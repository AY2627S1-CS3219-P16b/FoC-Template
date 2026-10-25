"""Public FAQ API. It never receives JWT keys or service-to-service credentials."""

import logging
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .config import EMBEDDING_MODEL, Settings
from .database import IndexNotReady, Store, create_database
from .embeddings import Embedder
from .knowledge import load_corpus
from .support import (
    ChatRequest, ChatResponse, ClaudeAnswerer, RateLimiter, SupportError,
    make_response, record_request,
)


def create_app(settings=None, *, store=None, embedder=None, answerer=None):
    settings = settings or Settings.from_env()
    # Components may be supplied for isolated tests without API calls or downloads.
    supplied = (store, embedder, answerer)

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        engine = None
        try:
            if supplied[0] is None:
                engine = create_database(settings.database_url)
            app.state.store = supplied[0] or Store(engine)
            app.state.store.initialize()
            load_corpus(settings.docs_dir)
            app.state.embedder = supplied[1] or Embedder(settings)
            app.state.answerer = supplied[2] or ClaudeAnswerer(settings)
            app.state.rate = RateLimiter(settings.requests_per_minute)
            app.state.slots = BoundedSemaphore(settings.max_concurrent_requests)
            yield
        finally:
            if getattr(app.state, "answerer", None):
                app.state.answerer.close()
            if engine is not None:
                engine.dispose()

    app = FastAPI(title="Friend on Campus FAQ Support", lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        # Avoid accepting oversized declared payloads on the paid public endpoint.
        if request.url.path == "/api/v1/faq/chat":
            try:
                too_large = int(request.headers.get("content-length", "0")) > 8192
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse({"detail": "Please send a shorter question."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health(request: Request):
        try:
            corpus = load_corpus(settings.docs_dir)
            indexed = request.app.state.store.status(corpus.version)
        except (SQLAlchemyError, OSError, ValueError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok", "index_ready": indexed,
                "chat_ready": indexed and bool(settings.anthropic_api_key),
                "embedding_model": EMBEDDING_MODEL}

    @app.post("/api/v1/faq/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, request: Request):
        state = request.app.state
        request_id = request.state.request_id
        started = perf_counter()
        details = {"question_length": len(body.question), "embedding_model": EMBEDDING_MODEL,
                   "answer_model": settings.anthropic_model}
        acquired = False
        outcome = "error"
        try:
            if not state.rate.allow():
                raise SupportError("rate_limited", 429)
            acquired = state.slots.acquire(blocking=False)
            if not acquired:
                raise SupportError("busy", 503)
            corpus = load_corpus(settings.docs_dir)
            details["knowledge_version"] = corpus.version
            if not state.store.status(corpus.version):
                raise IndexNotReady()
            retrieval_started = perf_counter()
            vector = state.embedder.query(body.question)
            evidence = state.store.retrieve(vector, corpus.version, settings.min_similarity)
            details["retrieval_ms"] = round((perf_counter() - retrieval_started) * 1000, 2)
            details["retrieved_ids"] = [row["id"] for row in evidence]
            details["scores"] = [round(row["score"], 4) for row in evidence]
            if not evidence:
                outcome = "not_found"
                return make_response(request_id)
            generation_started = perf_counter()
            answer, sources, usage = state.answerer.generate(body.question, evidence)
            details.update(usage)
            details["generation_ms"] = round((perf_counter() - generation_started) * 1000, 2)
            details["cited_ids"] = [row["id"] for row in sources]
            outcome = "answered" if answer else "not_found"
            return make_response(request_id, answer, sources)
        except IndexNotReady:
            outcome = "index_not_ready"
            return JSONResponse({"detail": "FAQ support is being updated. Please try again later.",
                                 "request_id": request_id}, status_code=503)
        except SupportError as error:
            outcome = error.code
            message = ("FAQ support is busy. Please wait a minute and try again."
                       if error.code in ("rate_limited", "busy") else
                       "FAQ support is temporarily unavailable. Please try again later.")
            return JSONResponse({"detail": message, "request_id": request_id},
                                status_code=error.status, headers={"Retry-After": "60"})
        except (SQLAlchemyError, OSError, ValueError, RuntimeError) as error:
            outcome = "service_unavailable"
            details["error_type"] = type(error).__name__
            return JSONResponse({"detail": "FAQ support is temporarily unavailable. Please try again later.",
                                 "request_id": request_id}, status_code=503)
        finally:
            if acquired:
                state.slots.release()
            details["total_ms"] = round((perf_counter() - started) * 1000, 2)
            record_request(state.store, request_id, outcome, details)

    return app
