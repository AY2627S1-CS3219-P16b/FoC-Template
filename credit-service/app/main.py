from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy import text

from .auth import CurrentUser, current_user, load_jwt_public_key
from .database import create_database_engine
from .schema import metadata
from .api_schemas import (
    CreditBalanceResponse,
    LedgerPageResponse,
    ReleaseCreditsRequest,
    ReservationResponse,
    ReserveCreditsRequest,
    TransferCreditsRequest,
)

from .credit_queries import (
    UserError,
    InsufficientCredits,
    NoChangeError,
    DuplicateReservationError,
    ReservationNotFoundError,
    ReservationStateError,
    get_account,
    reserve_credits,
    list_ledger,
    ensure_account,
    release_reservation,
    transfer_reservation
)

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
        title="Friend on Campus Credit Service",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/credits/me", response_model=CreditBalanceResponse)
    def get_credits(request: Request,
                    caller: CurrentUser = Depends(current_user)):
        with request.app.state.database.connect() as connection:
            try:
                return get_account(connection, caller.id)
            except UserError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Credit account has not been initialized.",
                ) from error

    @app.post("/api/v1/credits/me/initialize", response_model=CreditBalanceResponse)
    def initialize_credits(
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ):
        with request.app.state.database.begin() as connection:
            return ensure_account(connection, caller.id)

    @app.get("/api/v1/credits/me/ledger", response_model=LedgerPageResponse)
    def read_my_ledger(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        caller: CurrentUser = Depends(current_user),
    ):
        """The caller's credit ledger entries, newest first."""
        with request.app.state.database.connect() as connection:
            try:
                return list_ledger(connection, caller.id, page=page, page_size=page_size)
            except UserError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Credit account has not been initialized.",
                ) from error

    @app.post(
        "/api/v1/credits/reservations",
        response_model=ReservationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_reservation(
        body: ReserveCreditsRequest,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ):
        with request.app.state.database.begin() as connection:
            try:
                return reserve_credits(
                    connection,
                    order_id=body.order_id,
                    requester_user_id=caller.id,
                    amount=body.amount,
                    idempotency_key=body.idempotency_key,
                )
            except InsufficientCredits as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient available credits.",
                ) from error
            except DuplicateReservationError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error

    @app.post(
        "/api/v1/credits/reservations/{order_id}/release",
        response_model=ReservationResponse,
    )
    def release_credits(
        order_id: str,
        body: ReleaseCreditsRequest,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ):
        with request.app.state.database.begin() as connection:
            try:
                return release_reservation(
                    connection,
                    order_id=order_id,
                    requester_user_id=caller.id,
                    idempotency_key=body.idempotency_key,
                )
            except ReservationNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            except ReservationStateError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            except UserError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error

    @app.post(
        "/api/v1/credits/reservations/{order_id}/transfer",
        response_model=ReservationResponse,
    )
    def transfer_credits(
        order_id: str,
        body: TransferCreditsRequest,
        request: Request,
        caller: CurrentUser = Depends(current_user),
    ):
        with request.app.state.database.begin() as connection:
            try:
                return transfer_reservation(
                    connection,
                    order_id=order_id,
                    requester_user_id=caller.id,
                    courier_user_id=body.courier_user_id,
                    idempotency_key=body.idempotency_key,
                )
            except ReservationNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            except ReservationStateError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            except UserError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error

    return app
