import os
import logging
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger("auth_service")

# --- SETTINGS ---
SECRET_KEY = os.getenv("INTERNAL_SECRET_KEY", "nexus-super-secret-key-v7.6")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# Password Hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    tenant_id: int

class AuthService:
    @staticmethod
    def get_password_hash(password: str) -> str:
        # Bcrypt has a 72-byte limit. We truncate to ensure stability.
        # This is safe as anything beyond 72 is ignored by bcrypt anyway.
        safe_password = password[:72]
        return pwd_context.hash(safe_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        safe_password = plain_password[:72]
        return pwd_context.verify(safe_password, hashed_password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("user_id")
            email: str = payload.get("email")
            role: str = payload.get("role")
            tenant_id: int = payload.get("tenant_id")
            
            if user_id is None or email is None or role is None or tenant_id is None:
                logger.warning(f"❌ 401: Incomplete JWT payload. user_id={user_id}, email={email}, role={role}, tenant_id={tenant_id}")
                return None
                
            return TokenData(
                user_id=user_id,
                email=email,
                role=role,
                tenant_id=tenant_id
            )
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return None

    @staticmethod
    def log_protocol_omega_activation(email: str, activation_token: str):
        """
        Nexus Protocol Omega: 
        Always log the activation link in case of SMTP failure.
        """
        # Try to use PLATFORM_URL from env, otherwise fallback to frontend production URL
        base_url = os.getenv("PLATFORM_URL", "https://dentalogic-frontend.ugwrjq.easypanel.host")
        activation_url = f"{base_url}/activate?token={activation_token}&email={email}"
        
        logger.warning("🛡️ [PROTOCOL OMEGA] ACTIVATION LINK GENERATED (SMTP FAIL-SAFE)")
        logger.warning(f"🛡️ User: {email}")
        logger.warning(f"🛡️ Link: {activation_url}")
        logger.warning("🛡️ ---------------------------------------------------------")

auth_service = AuthService()
