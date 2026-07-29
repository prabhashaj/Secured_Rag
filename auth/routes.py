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


class UpdateMattersRequest(BaseModel):
    permitted_matters: list[str] = Field(description="List of permitted matter IDs")


async def get_current_user_dep(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency to extract and verify active user profile from Bearer token."""
    if not user_store:
        raise HTTPException(status_code=503, detail="Auth store not initialized")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    payload = verify_token(token, user_store=user_store)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid, expired, or revoked token")

    user = user_store.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    user["_token"] = token
    return user


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    """Register a new user account (permitted_matters default-assigned by system, not client-supplied)."""
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
            permitted_matters=None,  # Critical 1: Admin/system assigned only
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


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user_dep)):
    """Log out and revoke current token (Task 5)."""
    token = current_user.get("_token", "")
    if user_store and token:
        user_store.revoke_token(token)
    return {"status": "success", "message": "Token revoked successfully"}


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user_dep)):
    """Get active user profile from authorization header bearer token."""
    return user


# Admin endpoints router
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/users/{target_user_id}/matters")
async def update_user_matters(
    target_user_id: str,
    req: UpdateMattersRequest,
    current_user: dict = Depends(get_current_user_dep),
):
    """Admin-only endpoint to update permitted_matters for a user (Task 1)."""
    if current_user.get("role") not in ("admin", "Compliance Auditor"):
        raise HTTPException(status_code=403, detail="Admin or Compliance Auditor role required")

    if not user_store:
        raise HTTPException(status_code=503, detail="Auth store not initialized")

    target_user = user_store.get_user_by_id(target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{target_user_id}' not found")

    success = user_store.update_user_matters(target_user_id, req.permitted_matters)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user permitted matters")

    updated_user = user_store.get_user_by_id(target_user_id)
    return {
        "status": "success",
        "user_id": target_user_id,
        "permitted_matters": updated_user["permitted_matters"],
    }
