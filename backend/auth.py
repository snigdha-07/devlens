# auth.py
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# -- Config --------------------------------------------
# SECRET_KEY signs the JWT — change this to a long random string in production
# generate one with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY  = "SECRET_KEY"
ALGORITHM   = "HS256"
TOKEN_EXPIRE_HOURS = 24   # token valid for 24 hours

# -- Password hashing ------------------------------------
# bcrypt is the industry standard for password hashing
# it's slow by design — makes brute force attacks expensive
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Convert plain password to bcrypt hash for storage"""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Check if a plain password matches the stored hash"""
    return pwd_context.verify(plain, hashed)

# -- JWT token -----------------------------------------
# JWT = JSON Web Token
# Structure: header.payload.signature
# Payload contains user_id and expiry — backend can verify without DB lookup

def create_token(user_id: int, email: str, role: str = "student") -> str:
    """
    Create a signed JWT token.
    The token embeds user_id so we can identify the user
    on every subsequent request without hitting the DB.
    """
    payload = {
        "sub":     str(user_id),   # "sub" = subject (standard JWT claim)
        "email":   email,
        "role":  role,
        "exp":   datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# -- Token verification middleware ---------------------------
# OAuth2PasswordBearer tells FastAPI where to find the token in requests
# "tokenUrl" is the login endpoint — used by Swagger UI's Authorize button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency — called automatically on protected endpoints.
    Verifies the JWT and returns the user payload.
    
    Usage in endpoint:
        @app.get("/protected")
        async def protected(user = Depends(get_current_user)):
            user_id = user["user_id"]
    """
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Invalid or expired token",
        headers     = {"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email   = payload.get("email")
        role    = payload.get("role", "student")
        if user_id is None:
            raise credentials_exception
        return {"user_id": int(user_id), "email": email, "role": role}
    except JWTError:
        raise credentials_exception