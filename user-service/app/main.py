import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from fastapi import Body, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .database import Database, DuplicateEmailError
from .api_schemas import (
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    UserResponse,
)


ACCESS_TOKEN_TTL_SECONDS = 15 * 60 # 15 min sessions


def create_app(
    database_url: str | None = None,
    jwt_secret: str | None = None,
) -> FastAPI:
    
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    database = Database(database_url)

    password_hasher = PasswordHasher()
    # verify a hash even for unknown emails to disguise timing differences between valid and invalid logins
    dummy_password_hash = password_hasher.hash("TimingOnly1!")

    signing_secret = jwt_secret or os.getenv("JWT_SECRET")
    if not signing_secret:
        raise RuntimeError("JWT_SECRET is required")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        try:
            yield
        finally:
            database.close()

    app = FastAPI(
        title="Friend on Campus User Service",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.database = database

    cors_origins = os.getenv("CORS_ORIGINS")
    if not cors_origins:
        raise RuntimeError("CORS_ORIGINS is required")
    allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    if not allowed_origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one origin")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for item in error.errors():
            field = str(item["loc"][-1])
            message = item["msg"]
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            errors.append({"field": field, "message": message})
        return JSONResponse(status_code=422, content={"errors": errors})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/users/register",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        openapi_extra={
            "requestBody": {
                "content": {
                    "application/json": {"schema": RegistrationRequest.model_json_schema()}
                },
                "required": True,
            }
        },
    )
    def register(body: dict[str, object] = Body(...)) -> dict[str, object]:
        try:
            registration = RegistrationRequest.model_validate(body)
        except ValidationError as error:
            raise RequestValidationError(error.errors()) from error

        now = datetime.now(timezone.utc).isoformat()
        user = {
            "id": str(uuid4()),
            "email": registration.email,
            "password_hash": password_hasher.hash(registration.password),
            "display_name": registration.display_name,
            "contact_preference": registration.contact_preference,
            "telegram_handle": registration.telegram_handle,
            "phone_number": registration.phone_number,
            "profile_picture_url": registration.profile_picture_url,
            "auth_role": "USER",
            "active_role_mode": "REQUESTER",
            "account_status": "ACTIVE",
            "created_at": now,
        }
        try:
            return database.create_user(user)
        except DuplicateEmailError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "errors": [
                        {
                            "field": "email",
                            "message": "is already registered",
                        }
                    ]
                },
            )

    @app.post(
        "/api/v1/users/login",
        response_model=LoginResponse,
        openapi_extra={
            "requestBody": {
                "content": {"application/json": {"schema": LoginRequest.model_json_schema()}},
                "required": True,
            }
        },
    )
    def login(body: dict[str, object] = Body(...)) -> dict[str, object]:
        try:
            credentials = LoginRequest.model_validate(body)
        except ValidationError as error:
            raise RequestValidationError(error.errors()) from error

        user = database.find_user_by_email(credentials.email)
        password_hash = user["password_hash"] if user else dummy_password_hash

        try:
            password_matches = password_hasher.verify(password_hash, credentials.password)
        except (
            argon2_exceptions.VerificationError,
            argon2_exceptions.InvalidHashError,
        ):
            password_matches = False

        if not user or not password_matches or user["account_status"] != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        claims = {
            "sub": user["id"],
            "user_id": user["id"],
            "email": user["email"],
            "auth_role": user["auth_role"],
            "active_role_mode": user["active_role_mode"],
            "account_status": user["account_status"],
            "iat": issued_at,
            "exp": expires_at,
        }
        access_token = jwt.encode(claims, signing_secret, algorithm="HS256")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "display_name": user["display_name"],
                "auth_role": user["auth_role"],
                "active_role_mode": user["active_role_mode"],
                "account_status": user["account_status"],
            },
        }

    return app
