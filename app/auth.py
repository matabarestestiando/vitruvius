import secrets
from fastapi import HTTPException, Request
from .config import settings


def check_token(value):
    if not settings.owner_token or not secrets.compare_digest(
        value or "", "Bearer " + settings.owner_token
    ):
        raise HTTPException(401, "Se requiere el token del propietario")


def owner(request: Request):
    check_token(request.headers.get("authorization"))
