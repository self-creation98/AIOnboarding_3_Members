"""
FastAPI dependencies cho authentication.
Cung cấp get_current_user và get_current_active_user để bảo mật API endpoints.

Sử dụng Supabase auth.get_user(token) thay vì manual JWT decode
để tương thích với mọi thuật toán (HS256, ES256).
"""

import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.backend.database import get_supabase
from src.backend.schemas import UserInfo

logger = logging.getLogger(__name__)

# OAuth2 scheme — cho phép Swagger UI hiện nút "Authorize"
# tokenUrl trỏ đến login endpoint để Swagger tự gọi khi cần
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    """
    Verify JWT token qua Supabase API va tra ve thong tin user.

    Flow:
    1. Goi Supabase auth.get_user(token) de verify token
    2. Lay email tu Supabase user
    3. Query bang employees de lay thong tin day du (vai_tro, department...)
    4. Tra ve UserInfo

    Raises:
        HTTPException 401: Token khong hop le hoac het han
        HTTPException 403: User khong ton tai trong he thong nhan su
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token khong hop le hoac da het han",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 1: Verify token via Supabase API
    try:
        supabase = get_supabase()
        auth_response = supabase.auth.get_user(token)

        if not auth_response or not auth_response.user:
            raise credentials_exception

        email = auth_response.user.email
        if not email:
            raise credentials_exception

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Supabase token verification failed: {e}")
        raise credentials_exception

    # Step 2: Query employee from database
    try:
        result = (
            supabase.table("employees")
            .select("id, email, full_name, vai_tro, department, employee_code")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tai khoan khong co trong he thong nhan su",
            )

        emp = result.data[0]
        return UserInfo(
            id=emp["id"],
            email=emp["email"],
            full_name=emp["full_name"],
            vai_tro=emp["vai_tro"],
            department=emp["department"],
            employee_code=emp.get("employee_code"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error looking up employee: {e}")
        raise credentials_exception


async def get_current_active_user(
    current_user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    """
    Dependency chinh de bao mat endpoints.
    Ke thua get_current_user + co the them check (vd: account bi khoa).

    Usage:
        @app.get("/api/protected")
        async def protected(user: UserInfo = Depends(get_current_active_user)):
            return {"message": f"Hello {user.full_name}"}
    """
    # Co the them check: employee status, probation, etc.
    return current_user
