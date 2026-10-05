from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_database_engine
from .schema import metadata
from .api_schemas import (
    CreditBalanceResponse,
    ReserveCreditsRequest,
    TransferCreditsRequest,
    LedgerEntryResponse
)

def create_app() -> FastAPI:
    engine = create_database_engine()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        metadata.create_all(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Friend on Campus Credit Service",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}


    # @app.get("/api/v1/credits/me", response_model=CreditBalanceResponse)
    # def get_credits(request: Request):
    #     with request.app.state.database.connect() as connection:
    #         return [PlaceResponse(**row) for row in list_places(connection)]

    return app


# POST /api/v1/credits/me/initialize
# GET /api/v1/credits/me
# GET /api/v1/credits/me/ledger
# POST /api/v1/credits/reservations
# POST /api/v1/credits/reservations/{order_id}/release
# POST /api/v1/credits/reservations/{order_id}/transfer