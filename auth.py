from datetime import datetime, timedelta
from jose import JWTError, jwt
from core.config import settings
from schemas import TokenData
from core.utils import get_ist_now

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = get_ist_now() + expires_delta
    else:
        expire = get_ist_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        tenant_id: int = payload.get("tenant_id")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=role, tenant_id=tenant_id)
    except JWTError:
        raise credentials_exception
