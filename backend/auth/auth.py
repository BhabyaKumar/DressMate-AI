"""
JWT Authentication & User Management
=====================================
Handles user registration, login, token generation, and verification.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
import hashlib
from fastapi import Depends, HTTPException, status, Header
from pydantic import BaseModel
from database.config import (
    insert_user,
    get_user_by_email,
    db,
)

# ── Configuration ──────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "dressmate-salt-change-in-production")

# ── Password utilities ─────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash a password using SHA256 with salt."""
    salted = PASSWORD_SALT + password
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(plain_password) == hashed_password


# ── Models ─────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    """Registration request model."""
    email: str
    password: str
    name: str = "User"


class UserLogin(BaseModel):
    """Login request model."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfile(BaseModel):
    """User profile model."""
    user_id: str
    email: str
    name: str
    skin_tone: Optional[str] = None
    preferred_colors: list = []
    preferred_types: list = []


# ── JWT utilities ──────────────────────────────────────────────────────────
def create_access_token(user_id: str, email: str, expires_in_hours: int = JWT_EXPIRATION_HOURS) -> str:
    """Create a JWT access token."""
    expire = datetime.utcnow() + timedelta(hours=expires_in_hours)
    payload = {
        "user_id": str(user_id),
        "email": email,
        "exp": expire,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ── Dependency: Current user ───────────────────────────────────────────────
async def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract and verify user from JWT token in Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Authorization: Bearer <token>",
        )
    
    payload = verify_token(token)
    return payload


async def get_current_user_optional(authorization: str = Header(None)) -> Optional[dict]:
    """Extract and verify user from JWT token in Authorization header (optional)."""
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        payload = verify_token(token)
        return payload
    except:
        return None


# ── User operations ────────────────────────────────────────────────────────
def register_user(email: str, password: str, name: str = "User") -> str:
    """
    Register a new user.
    Returns user_id on success.
    Raises HTTPException if email already exists.
    """
    # Check if user exists
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user document
    user_data = {
        "email": email,
        "password_hash": hash_password(password),
        "name": name,
        "created_at": datetime.utcnow(),
        "skin_tone": None,
        "preferred_colors": [],
        "preferred_types": [],
        "recommendation_count": 0,
    }
    
    user_id = insert_user(user_data)
    return user_id


def authenticate_user(email: str, password: str) -> dict:
    """
    Authenticate user by email and password.
    Returns user document if successful.
    Raises HTTPException if credentials invalid.
    """
    user = get_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


def update_user_preferences(user_id: str, skin_tone: str = None, colors: list = None, types: list = None):
    """Update user preferences in MongoDB."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    
    from bson.objectid import ObjectId
    
    update_data = {}
    if skin_tone:
        update_data["skin_tone"] = skin_tone
    if colors:
        update_data["preferred_colors"] = colors
    if types:
        update_data["preferred_types"] = types
    
    if update_data:
        try:
            db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
        except Exception:
            db.users.update_one(
                {"_id": int(user_id)},
                {"$set": update_data}
            )
