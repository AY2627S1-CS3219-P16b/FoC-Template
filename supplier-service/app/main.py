from contextlib import asynccontextmanager
import os

import httpx
from math import ceil
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy import text

from .admin_queries import (
    DuplicatePlaceError,
    DuplicateSupplierError,
    NoChangeError,
    UnknownPlaceError,
    count_audit_logs,
    create_place,
    create_supplier,
    deactivate_supplier,
    list_audit_logs,
    update_supplier,
)
from .api_schemas import (
    AuditLogPage,
    PlaceCreate,
    PlaceResponse,
    SupplierCreate,
    SupplierPage,
    SupplierResponse,
    SupplierUpdate,
)
from .auth import CurrentUser, admin_reason, current_user, require_admin
from .classification import SUPPLIER_TYPES
from .database import create_database_engine
from .schema import metadata
from .supplier_queries import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_SORT,
    MAX_PAGE_SIZE,
    SORT_OPTIONS,
    count_suppliers,
    get_supplier,
    list_places,
    list_suppliers,
    resolve_place_id,
)


def create_app() -> FastAPI:
    engine = create_database_engine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            # Creates missing tables; existing supplier records are preserved.
            metadata.create_all(engine)
            # Open a real connection at startup to verify PostgreSQL is available.
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.database = engine
            with httpx.Client(
                base_url=os.getenv("USER_SERVICE_URL", "http://127.0.0.1:8000"),
                timeout=3.0, follow_redirects=False, trust_env=False,
            ) as user_client:
                app.state.user_client = user_client
                yield
        finally:
            engine.dispose()

    app = FastAPI(title="Friend on Campus Supplier Service", lifespan=lifespan,
                  dependencies=[Depends(current_user)])

    @app.get("/api/v1/places", response_model=list[PlaceResponse])
    def get_places(request: Request):
        """Every place, for the browse filter and the admin place picker."""
        with request.app.state.database.connect() as connection:
            return [PlaceResponse(**row) for row in list_places(connection)]

    @app.get("/api/v1/suppliers", response_model=SupplierPage)
    def browse_suppliers(
        request: Request,
        q: str | None = Query(None, max_length=200,
                              description="Matches supplier name or place name"),
        type: str | None = Query(None, description=f"One of {', '.join(SUPPLIER_TYPES)}"),
        place: str | None = Query(None, max_length=200,
                                  description="Place id or search key; includes nested places"),
        sort: str = Query(DEFAULT_SORT, description=f"One of {', '.join(SORT_OPTIONS)}"),
        page: int = Query(1, ge=1),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        include_inactive: bool = Query(
            False, description="Admin only: also return hidden suppliers"),
        caller: CurrentUser = Depends(current_user),
    ):
        # Browsing hides deactivated suppliers; an admin needs to see them to
        # restore one, so the flag is refused for everyone else.
        if include_inactive and caller.auth_role != "ADMIN":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Admin access is required."
            )
        with request.app.state.database.connect() as connection:
            place_id = None
            if place is not None:
                try:
                    place_id = resolve_place_id(connection, place)
                except ValueError as error:
                    raise HTTPException(status_code=422, detail="Invalid place name.") from error
                if place_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Unknown place {place!r}.",
                    )
            filters = {
                "search": q,
                "supplier_type": type,
                "place_id": place_id,
                "include_inactive": include_inactive,
            }
            try:
                total = count_suppliers(connection, **filters)
                rows = list_suppliers(
                    connection, page=page, page_size=page_size, sort=sort, **filters
                )
            except ValueError as error:
                # Invalid category, search or sort: a client mistake, not a server fault.
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error),
                ) from error

        return SupplierPage(
            items=[SupplierResponse.from_row(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    @app.get("/api/v1/suppliers/{supplier_id}", response_model=SupplierResponse)
    def read_supplier(supplier_id: UUID, request: Request):
        """One supplier, active or not, so existing orders stay resolvable."""
        with request.app.state.database.connect() as connection:
            row = get_supplier(connection, supplier_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found."
            )
        return SupplierResponse.from_row(row)

    # Admin endpoints. require_admin re-uses the already-verified caller, so a
    # request still costs one User Service call, and denies with 403 rather
    # than 401: the caller is known, the role is not enough.

    @app.post("/api/v1/suppliers", response_model=SupplierResponse,
              status_code=status.HTTP_201_CREATED)
    def add_supplier(request: Request, body: SupplierCreate,
                     admin: CurrentUser = Depends(require_admin)):
        """Add a supplier to an existing place.

        No X-Admin-Reason: the created record is its own explanation. Changing
        or hiding one does need a reason, as in User Service, where registering
        an account needs none but altering one does.
        """
        with request.app.state.database.begin() as connection:
            try:
                row = create_supplier(
                    connection, actor_id=UUID(admin.id), values=body.model_dump(),
                )
            except UnknownPlaceError as error:
                raise HTTPException(404, "Unknown place.") from error
            except DuplicateSupplierError as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "A supplier with this name already exists at that place and floor.",
                ) from error
        return SupplierResponse.from_row(row)

    @app.patch("/api/v1/suppliers/{supplier_id}", response_model=SupplierResponse)
    def edit_supplier(supplier_id: UUID, request: Request, body: SupplierUpdate,
                      admin: CurrentUser = Depends(require_admin),
                      reason: str = Depends(admin_reason)):
        """Change the supplied fields. Setting is_active restores a hidden supplier."""
        with request.app.state.database.begin() as connection:
            try:
                row = update_supplier(
                    connection, actor_id=UUID(admin.id), supplier_id=supplier_id,
                    changes=body.model_dump(exclude_unset=True), reason=reason,
                )
            except UnknownPlaceError as error:
                raise HTTPException(404, "Unknown place.") from error
            except DuplicateSupplierError as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "A supplier with this name already exists at that place and floor.",
                ) from error
            except NoChangeError as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Supplier is already in that state."
                ) from error
        if row is None:
            raise HTTPException(404, "Supplier not found.")
        return SupplierResponse.from_row(row)

    @app.delete("/api/v1/suppliers/{supplier_id}", response_model=SupplierResponse)
    def remove_supplier(supplier_id: UUID, request: Request,
                        admin: CurrentUser = Depends(require_admin),
                        reason: str = Depends(admin_reason)):
        """Hide a supplier from browsing. The record stays so orders resolve."""
        with request.app.state.database.begin() as connection:
            try:
                row = deactivate_supplier(
                    connection, actor_id=UUID(admin.id),
                    supplier_id=supplier_id, reason=reason,
                )
            except NoChangeError as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Supplier is already inactive."
                ) from error
        if row is None:
            raise HTTPException(404, "Supplier not found.")
        return SupplierResponse.from_row(row)

    @app.post("/api/v1/places", response_model=PlaceResponse,
              status_code=status.HTTP_201_CREATED)
    def add_place(request: Request, body: PlaceCreate,
                  admin: CurrentUser = Depends(require_admin)):
        """Add a place, optionally inside an existing one."""
        with request.app.state.database.begin() as connection:
            try:
                row = create_place(
                    connection, actor_id=UUID(admin.id), name=body.name,
                    parent_id=body.parent_id,
                )
            except UnknownPlaceError as error:
                raise HTTPException(404, "Unknown parent place.") from error
            except DuplicatePlaceError as error:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "A place with an equivalent name already exists.",
                ) from error
            except ValueError as error:
                # A name with no letters or digits has no usable search key.
                raise HTTPException(422, str(error)) from error
        return PlaceResponse(**row)

    # Not /api/v1/admin/...: User Service already owns that path, and two
    # services answering the same URL is ambiguous behind a proxy or gateway.
    @app.get("/api/v1/supplier-changes", response_model=AuditLogPage)
    def read_audit_logs(request: Request, page: int = Query(1, ge=1),
                        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
                        admin: CurrentUser = Depends(require_admin)):
        """Every recorded admin change, newest first."""
        with request.app.state.database.connect() as connection:
            total = count_audit_logs(connection)
            rows = list_audit_logs(connection, page=page, page_size=page_size)
        return AuditLogPage(
            items=rows, page=page, page_size=page_size, total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    return app
