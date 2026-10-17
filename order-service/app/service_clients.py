"""Small HTTP clients for Supplier snapshots and idempotent credit actions."""

import json
from http.client import HTTPException as HTTPProtocolError
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictBool

from .api_schemas import RequiredText


def _request_json(url: str, headers: dict, payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


class _Place(BaseModel):
    name: RequiredText
    parent_name: str | None = None


class _Supplier(BaseModel):
    id: UUID
    name: RequiredText = Field(max_length=200)
    place: _Place
    floor: str | None = None
    location_description: str | None = None
    pickup_instructions: str | None = None
    is_active: StrictBool
    is_open_now: StrictBool


def supplier_snapshot(base_url: str, supplier_id: str, token: str) -> tuple[str, str]:
    """Validate supplier identity/availability and snapshot server-owned pickup details."""
    try:
        supplier_id = str(UUID(supplier_id))
    except ValueError:
        raise HTTPException(422, "supplier_id must be a UUID.") from None
    try:
        supplier = _Supplier.model_validate(_request_json(
            f"{base_url.rstrip('/')}/api/v1/suppliers/{supplier_id}",
            {"Authorization": token},
        ))
        if str(supplier.id) != supplier_id:
            raise ValueError("Supplier identity mismatch")
    except HTTPError as error:
        code = error.code if error.code in (401, 403, 404, 422) else 502
        raise HTTPException(code, "Supplier lookup was rejected.") from None
    except (URLError, TimeoutError, OSError, HTTPProtocolError):
        raise HTTPException(503, "Supplier Service is unavailable.") from None
    except (ValueError, UnicodeError):
        raise HTTPException(502, "Supplier Service returned invalid details.") from None
    if not supplier.is_active or not supplier.is_open_now:
        raise HTTPException(409, "Supplier is inactive or currently closed.")
    location = ", ".join(part.strip() for part in (
        supplier.place.parent_name, supplier.place.name, supplier.floor,
        supplier.location_description, supplier.pickup_instructions,
    ) if part and part.strip())
    return supplier.name, location


class _Reservation(BaseModel):
    order_id: str
    requester_user_id: str
    courier_user_id: str | None = None
    amount: int = Field(strict=True, gt=0)
    status: Literal["RESERVED", "RELEASED", "TRANSFERRED"]


class InsufficientCredits(Exception):
    """Credit Service definitively refused a new reservation for insufficient funds."""


class CreditClient:
    def __init__(self, base_url: str, service_key: str):
        if not service_key.strip():
            raise ValueError("ORDER_SERVICE_KEY is required")
        self.url = base_url.rstrip("/") + "/api/v1/credits/reservations"
        self.headers = {"X-Service-Key": service_key}

    def _request(self, url: str, payload: dict | None = None) -> _Reservation:
        return _Reservation.model_validate(_request_json(url, self.headers, payload))

    @staticmethod
    def _validate(reservation: _Reservation, job: dict) -> None:
        if (reservation.order_id != job["order_id"]
                or reservation.requester_user_id != job["requester_user_id"]
                or reservation.amount != job["credit_amount"]):
            raise RuntimeError("Credit reservation does not match the order")
        if (reservation.status == "TRANSFERRED"
                and reservation.courier_user_id != job["courier_user_id"]):
            raise RuntimeError("Credit recipient does not match the assigned courier")

    def apply(self, job: dict) -> None:
        """Reconcile first so crashes after a credit commit are safe to replay."""
        operation = job["operation"]
        states = {"RESERVE": ("RESERVING",), "RELEASE": ("CANCELLING", "EXPIRING"),
                  "TRANSFER": ("COMPLETING",)}
        if job["order_status"] not in states.get(operation, ()):
            raise RuntimeError("Credit job does not match the pending order state")
        target = {"RESERVE": "RESERVED", "RELEASE": "RELEASED", "TRANSFER": "TRANSFERRED"}[operation]
        order_url = self.url + "/" + quote(job["order_id"], safe="")
        try:
            reservation = self._request(order_url)
        except HTTPError as error:
            if error.code != 404:
                raise
            reservation = None
        if reservation is not None:
            self._validate(reservation, job)
            if reservation.status == target:
                return
            if reservation.status != "RESERVED":
                raise RuntimeError("Reservation has an incompatible terminal state")
        elif operation != "RESERVE":
            raise RuntimeError("Credit reservation is missing")

        payload = {"requester_user_id": job["requester_user_id"],
                   "idempotency_key": f"order:{job['order_id']}:{operation.lower()}"}
        url = order_url + "/" + operation.lower()
        if operation == "RESERVE":
            url = self.url
            payload.update(order_id=job["order_id"], amount=job["credit_amount"])
        elif operation == "TRANSFER":
            payload["courier_user_id"] = job["courier_user_id"]
        try:
            result = self._request(url, payload)
        except HTTPError as error:
            if operation == "RESERVE" and error.code == 409:
                try:
                    detail = json.load(error)
                except (ValueError, UnicodeError):
                    detail = None
                if isinstance(detail, dict) and detail.get("detail") == "Insufficient available credits.":
                    raise InsufficientCredits from None
            raise
        self._validate(result, job)
        if result.status != target:
            raise RuntimeError("Credit Service did not confirm the requested operation")
