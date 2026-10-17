"""Order Service app setup and API endpoint skeletons."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Body, Depends, FastAPI, Header, Query, Request, status
from sqlalchemy import text

from .auth import CurrentUser, current_user, load_jwt_public_key
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

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        """Check service and database availability."""
        pass

    @app.post("/api/v1/orders", status_code=status.HTTP_202_ACCEPTED)
    def create_order(
        request: Request,
        body: dict[str, object] = Body(...),
        idempotency_key: str = Header(..., min_length=1, max_length=200),
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Validate requester and supplier details; create an order pending credits.

        Replace the generic body with CreateOrderRequest once schemas are defined.
        """
        pass

    @app.get("/api/v1/orders")
    def list_orders(
        request: Request,
        status: str = Query("OPEN"),
        supplier_id: str | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Browse visible orders filtered by status and supplier."""
        pass

    # Register /me before /{order_id} so it is not treated as an order ID.
    @app.get("/api/v1/orders/me")
    def get_user_orders(
        request: Request,
        role: Literal["requester", "courier"] = Query(...),
        status: str | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """List the caller's requests or courier assignments."""
        pass

    @app.get("/api/v1/orders/{order_id}")
    def get_order_details(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Read an order visible to the caller."""
        pass

    @app.post("/api/v1/orders/{order_id}/accept")
    def assign_courier(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Assign the calling courier to an unexpired open order."""
        pass

    @app.post("/api/v1/orders/{order_id}/pickup")
    def mark_items_collected(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Let the assigned courier mark the items collected."""
        pass

    @app.post("/api/v1/orders/{order_id}/deliver")
    def mark_delivery_completed(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Let the assigned courier mark delivery, awaiting requester receipt."""
        pass

    @app.post("/api/v1/orders/{order_id}/confirm", status_code=status.HTTP_202_ACCEPTED)
    def confirm_order_receipt(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Let the requester confirm receipt and queue the credit transfer."""
        pass

    @app.post("/api/v1/orders/{order_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    def cancel_open_order(
        order_id: str,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Let the requester cancel an open order and queue credit release."""
        pass

    @app.get("/api/v1/orders/{order_id}/history")
    def get_order_history(
        order_id: str,
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ) -> dict[str, object]:
        """Read chronological history for the requester or assigned courier."""
        pass

    return app
