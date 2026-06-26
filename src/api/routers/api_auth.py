from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os

from src.api.jwt_auth import create_token
from src.api.throttle import enforce_rate_limit, record_failure, record_success, passwords_match

router = APIRouter(prefix="/api/auth", tags=["mobile-auth"])


class TokenRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str


@router.post("/token", response_model=TokenResponse)
def get_token(body: TokenRequest, request: Request) -> TokenResponse:
    key = enforce_rate_limit(request)
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    spectator_password = os.environ.get("SPECTATOR_PASSWORD", "")
    if passwords_match(body.password, admin_password):
        record_success(key)
        return TokenResponse(token=create_token("admin"), role="admin")
    if passwords_match(body.password, spectator_password):
        record_success(key)
        return TokenResponse(token=create_token("spectator"), role="spectator")
    record_failure(key)
    raise HTTPException(status_code=401, detail="Invalid password")
