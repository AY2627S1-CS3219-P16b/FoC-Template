"""Order Service app setup and HTTP endpoints."""

from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from .auth import CurrentUser, current_user, load_jwt_public_key
from .api_schemas import (
    CreateOrderRequest,
    HealthResponse,
    OrderHistoryPageResponse,
    OrderPageResponse,
    OrderResponse,
    OrderRole,
    OrderStatus,
    RequiredText,
)
from .database import create_database_engine
from .schema import metadata, orders
from .service_clients import supplier_snapshot

from . import order_queries as queries


def create_app() -> FastAPI:
    engine = create_database_engine()
    public_key = load_jwt_public_key()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            metadata.create_all(engine)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.database = engine
            app.state.jwt_public_key = public_key
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Friend on Campus Order Service",
        version="1.0.0",
        lifespan=lifespan,
    )

    errors = {
        queries.OrderNotFoundError: (404, None),
        queries.OrderAccessDeniedError: (403, None),
        queries.OrderStateError: (409, None),
        queries.OrderIdempotencyConflict: (409, None),
        ValidationError: (500, "Invalid service response."),
        ValueError: (422, None),
        IntegrityError: (409, "Conflicting order operation."),
        OperationalError: (503, "Database unavailable."),
    }

    async def query_error(request: Request, error: Exception) -> JSONResponse:
        code, message = next((config for cls, config in errors.items()
                              if isinstance(error, cls)), (500, "Internal server error."))
        return JSONResponse(status_code=code, content={"detail": message or str(error)})

    for error_type in errors:
        app.add_exception_handler(error_type, query_error)

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        try:
            with request.app.state.database.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(503, "Database unavailable.") from None
        return HealthResponse(status="ok")

    @app.post("/api/v1/orders", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
    def create_order(
        request: Request,
        body: CreateOrderRequest,
        idempotency_key: RequiredText = Header(..., max_length=200, alias="Idempotency-Key"),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Validate requester and supplier details; create an order pending credits."""
        if caller.active_role_mode != "REQUESTER":
            raise HTTPException(403, "Switch to requester mode to create an order.")

        # Replays retain the supplier snapshot, even if the supplier is now closed.
        with request.app.state.database.connect() as connection:
            existing = connection.execute(select(orders).where(
                orders.c.requester_user_id == caller.id,
                orders.c.idempotency_key == idempotency_key,
            )).mappings().one_or_none()
        snapshot = (existing["supplier_name"], existing["pickup_location"]) if existing else supplier_snapshot(
            os.getenv("SUPPLIER_SERVICE_URL", "http://localhost:8001"),
            body.supplier_id, request.headers["authorization"],
        )
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.create_order(
                connection, requester_user_id=caller.id,
                supplier_name=snapshot[0], pickup_location=snapshot[1],
                idempotency_key=idempotency_key, **body.model_dump(),
            ))

    @app.get("/api/v1/orders", response_model=OrderPageResponse)
    def list_orders(
        request: Request,
        status: OrderStatus = Query("OPEN"),
        supplier_id: RequiredText | None = Query(None, max_length=100),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderPageResponse:
        """Browse visible orders filtered by status and supplier."""
        with request.app.state.database.connect() as connection:
            return OrderPageResponse.model_validate(queries.list_orders(
                connection, viewer_user_id=caller.id, status=status,
                supplier_id=supplier_id, page=page, page_size=page_size,
            ))

    # Register /me before /{order_id} so it is not treated as an order ID.
    @app.get("/api/v1/orders/me", response_model=OrderPageResponse)
    def get_user_orders(
        request: Request,
        role: OrderRole = Query(...),
        status: OrderStatus | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderPageResponse:
        """List the caller's requests or courier assignments."""
        with request.app.state.database.connect() as connection:
            return OrderPageResponse.model_validate(queries.get_user_orders(
                connection, caller.id, role=role, status=status,
                page=page, page_size=page_size,
            ))

    @app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
    def get_order_details(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Read an order visible to the caller."""
        with request.app.state.database.connect() as connection:
            return OrderResponse.model_validate(queries.get_order_details(
                connection, order_id, viewer_user_id=caller.id,
            ))

    @app.post("/api/v1/orders/{order_id}/accept", response_model=OrderResponse)
    def assign_courier(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Assign the calling courier to an unexpired open order."""
        if caller.active_role_mode != "COURIER":
            raise HTTPException(403, "Switch to courier mode to accept an order.")
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.assign_courier(
                connection, order_id, courier_user_id=caller.id,
            ))

    @app.post("/api/v1/orders/{order_id}/pickup", response_model=OrderResponse)
    def mark_items_collected(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the assigned courier mark the items collected."""
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.mark_items_collected(
                connection, order_id, courier_user_id=caller.id,
            ))

    @app.post("/api/v1/orders/{order_id}/deliver", response_model=OrderResponse)
    def mark_delivery_completed(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the assigned courier mark delivery, awaiting requester receipt."""
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.mark_delivery_completed(
                connection, order_id, courier_user_id=caller.id,
            ))

    @app.post("/api/v1/orders/{order_id}/confirm", response_model=OrderResponse,
              status_code=status.HTTP_202_ACCEPTED)
    def confirm_order_receipt(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the requester confirm receipt and queue the credit transfer."""
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.confirm_order_receipt(
                connection, order_id, requester_user_id=caller.id,
            ))

    @app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderResponse,
              status_code=status.HTTP_202_ACCEPTED)
    def cancel_open_order(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the requester cancel an open order and queue credit release."""
        with request.app.state.database.begin() as connection:
            return OrderResponse.model_validate(queries.cancel_open_order(
                connection, order_id, requester_user_id=caller.id,
            ))

    @app.get("/api/v1/orders/{order_id}/history", response_model=OrderHistoryPageResponse)
    def get_order_history(
        order_id: RequiredText,
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderHistoryPageResponse:
        """Read chronological history for the requester or assigned courier."""
        with request.app.state.database.connect() as connection:
            return OrderHistoryPageResponse.model_validate(queries.get_order_history(
                connection, order_id, viewer_user_id=caller.id,
                page=page, page_size=page_size,
            ))

    return app
