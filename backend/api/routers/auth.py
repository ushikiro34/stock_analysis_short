"""
Simple auth — 개인용 도구용 최소 인증
APP_USERNAME / APP_PASSWORD 환경변수로 아이디/비밀번호 설정.
미설정 시 모든 로그인 허용 (개발 환경 배려).
"""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["🔐 Auth"])

# 유효 토큰 저장소 {token: expiry_datetime}
_valid_tokens: dict[str, datetime] = {}
_TOKEN_TTL_HOURS = 24 * 7  # 7일


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str = ""
    message: str = ""


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    expected_user = os.getenv("APP_USERNAME", "")
    expected_pass = os.getenv("APP_PASSWORD", "")

    # 환경변수 미설정 시 항상 허용 (개발 모드)
    if not expected_user and not expected_pass:
        token = secrets.token_urlsafe(32)
        _valid_tokens[token] = datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)
        return LoginResponse(success=True, token=token)

    if req.username == expected_user and req.password == expected_pass:
        token = secrets.token_urlsafe(32)
        _valid_tokens[token] = datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)
        return LoginResponse(success=True, token=token)

    return LoginResponse(success=False, message="아이디 또는 비밀번호가 올바르지 않습니다.")


@router.get("/check")
async def check_token(token: str = ""):
    _cleanup_expired()
    if not token:
        return {"valid": False}
    # 환경변수 미설정 시 항상 유효 처리
    if not os.getenv("APP_USERNAME") and not os.getenv("APP_PASSWORD"):
        return {"valid": True}
    valid = token in _valid_tokens and _valid_tokens[token] > datetime.utcnow()
    return {"valid": valid}


@router.post("/logout")
async def logout(token: str = ""):
    _valid_tokens.pop(token, None)
    return {"success": True}


def _cleanup_expired():
    now = datetime.utcnow()
    expired = [t for t, exp in _valid_tokens.items() if exp <= now]
    for t in expired:
        del _valid_tokens[t]
