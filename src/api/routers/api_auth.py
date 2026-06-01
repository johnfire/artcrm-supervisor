from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

from src.api.jwt_auth import create_token

router = APIRouter(prefix="/api/auth", tags=["mobile-auth"])


class TokenRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str


@router.post("/token", response_model=TokenResponse)
def get_token(body: TokenRequest) -> TokenResponse:
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    spectator_password = os.environ.get("SPECTATOR_PASSWORD", "")
    if admin_password and body.password == admin_password:
        return TokenResponse(token=create_token("admin"), role="admin")
    if spectator_password and body.password == spectator_password:
        return TokenResponse(token=create_token("spectator"), role="spectator")
    raise HTTPException(status_code=401, detail="Invalid password")
