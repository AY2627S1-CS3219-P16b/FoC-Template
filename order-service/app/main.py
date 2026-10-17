"""Order Service app setup and API endpoint skeletons."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Query, Request, status
from sqlalchemy import text

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
from .schema import metadata


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

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        """Check service and database availability."""
        pass

    @app.post("/api/v1/orders", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
    def create_order(
        request: Request,
        body: CreateOrderRequest,
        idempotency_key: RequiredText = Header(..., max_length=200, alias="Idempotency-Key"),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Validate requester and supplier details; create an order pending credits."""
        pass

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
        pass

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
        pass

    @app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
    def get_order_details(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Read an order visible to the caller."""
        pass

    @app.post("/api/v1/orders/{order_id}/accept", response_model=OrderResponse)
    def assign_courier(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Assign the calling courier to an unexpired open order."""
        pass

    @app.post("/api/v1/orders/{order_id}/pickup", response_model=OrderResponse)
    def mark_items_collected(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the assigned courier mark the items collected."""
        pass

    @app.post("/api/v1/orders/{order_id}/deliver", response_model=OrderResponse)
    def mark_delivery_completed(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the assigned courier mark delivery, awaiting requester receipt."""
        pass

    @app.post("/api/v1/orders/{order_id}/confirm", response_model=OrderResponse,
              status_code=status.HTTP_202_ACCEPTED)
    def confirm_order_receipt(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the requester confirm receipt and queue the credit transfer."""
        pass

    @app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderResponse,
              status_code=status.HTTP_202_ACCEPTED)
    def cancel_open_order(
        order_id: RequiredText,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> OrderResponse:
        """Let the requester cancel an open order and queue credit release."""
        pass

    @app.get("/api/v1/orders/{order_id}/history", response_model=OrderHistoryPageResponse)
    def get_order_history(
        order_id: RequiredText,
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> OrderHistoryPageResponse:
        """Read chronological history for the requester or assigned courier."""
        pass

    return app
