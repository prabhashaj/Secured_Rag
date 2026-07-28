"""
Auth Routes — FastAPI endpoints for Sign Up, Login, and User Profile.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field, EmailStr

from auth.store import UserStore, verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

user_store: Optional[UserStore] = None


def set_user_store(store: UserStore) -> None:
    """Set global user store for auth routes."""
    global user_store
    user_store = store


class SignupRequest(BaseModel):
    email: str = Field(description="User email address")
    full_name: str = Field(description="Full name of user")
    password: str = Field(description="Account password")
    role: str = Field(default="Senior Attorney", description="Role or title")
    permitted_matters: list[str] = Field(
        default_factory=lambda: ["Matter_101", "Matter_102"],
        description="Assigned legal matter permission groups",
    )


class LoginRequest(BaseModel):
    email: str = Field(description="User email address")
    password: str = Field(description="Account password")


class AuthResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    permitted_matters: list[str]
    token: str


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    """Register a new user account."""
    if not user_store:
        raise HTTPException(status_code=503, detail="Auth store not initialized")

    existing = user_store.get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Account with this email already exists")

    try:
        user = user_store.create_user(
            email=req.email,
            full_name=req.full_name,
            password=req.password,
            role=req.role,
            permitted_matters=req.permitted_matters,
        )
        return user
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Log in to an existing account."""
    if not user_store:
        raise HTTPException(status_code=503, detail="Auth store not initialized")

    user = user_store.authenticate_user(email=req.email, password=req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return user


@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get active user profile from authorization header bearer token."""
    if not user_store:
        raise HTTPException(status_code=503, detail="Auth store not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = user_store.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    return user
