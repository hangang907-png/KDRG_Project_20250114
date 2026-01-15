"""
인증 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import jwt
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# 모델 정의
class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserInfo(BaseModel):
    username: str
    role: str
    department: Optional[str] = None


# 간단한 인메모리 사용자 저장소 (프로덕션에서는 DB 사용)
USERS_DB = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "department": "보건의료정보관리과"
    },
    "user": {
        "password_hash": hashlib.sha256("user123".encode()).hexdigest(),
        "role": "user",
        "department": "원무과"
    }
}


def verify_password(plain_password: str, password_hash: str) -> bool:
    """비밀번호 검증"""
    return hashlib.sha256(plain_password.encode()).hexdigest() == password_hash


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """JWT 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[UserInfo]:
    """현재 사용자 정보 조회"""
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            return None
        
        user = USERS_DB.get(username)
        if user is None:
            return None
        
        return UserInfo(
            username=username,
            role=user["role"],
            department=user.get("department")
        )
    except jwt.PyJWTError:
        return None


async def require_auth(token: str = Depends(oauth2_scheme)) -> UserInfo:
    """인증 필수"""
    user = await get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def require_admin(user: UserInfo = Depends(require_auth)) -> UserInfo:
    """관리자 권한 필수"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return user


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """로그인하여 액세스 토큰 발급"""
    user = USERS_DB.get(form_data.username)
    
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자명 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token = create_access_token(
        data={"sub": form_data.username, "role": user["role"]}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=Token)
async def login(user_login: UserLogin):
    """JSON 바디로 로그인"""
    user = USERS_DB.get(user_login.username)
    
    if not user or not verify_password(user_login.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자명 또는 비밀번호가 올바르지 않습니다."
        )
    
    access_token = create_access_token(
        data={"sub": user_login.username, "role": user["role"]}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(user: UserInfo = Depends(require_auth)):
    """현재 로그인한 사용자 정보"""
    return user


@router.post("/logout")
async def logout():
    """로그아웃 (클라이언트에서 토큰 삭제)"""
    return {"message": "로그아웃 되었습니다."}
