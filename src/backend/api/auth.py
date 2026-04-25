"""
Auth API endpoints — UC-09: Đăng nhập & xác thực.

Endpoints:
- POST /api/auth/login  — Đăng nhập bằng email/password
- GET  /api/auth/me     — Lấy thông tin user hiện tại (protected)
"""

import logging
import sys
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.config import ALLOWED_EMAIL_DOMAINS
from src.backend.database import get_supabase
from src.backend.schemas import TokenResponse, UserInfo, ErrorResponse
from src.backend.api.deps import get_current_active_user

# Fix Windows console encoding for Vietnamese debug output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _validate_email_domain(email: str) -> None:
    """
    Kiểm tra email có thuộc domain cho phép không.
    Raises HTTPException 403 nếu domain không hợp lệ.
    """
    user_domain = email.split("@")[-1].strip().lower()
    allowed = [d.strip().lower() for d in ALLOWED_EMAIL_DOMAINS]

    # === DEBUG LOGGING ===
    print(f"DEBUG: Email input: '{email}'")
    print(f"DEBUG: Domain extracted: '{user_domain}'")
    print(f"DEBUG: ALLOWED_EMAIL_DOMAINS: {ALLOWED_EMAIL_DOMAINS}")
    print(f"DEBUG: Allowed (after strip/lower): {allowed}")
    print(f"DEBUG: Domain '{user_domain}' in allowed = {user_domain in allowed}")
    # === END DEBUG ===

    if user_domain not in allowed:
        allowed_str = ", ".join(f"@{d}" for d in allowed)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Chỉ tài khoản công ty ({allowed_str}) mới được phép truy cập. "
                   f"Email '{email}' có domain '{user_domain}' không nằm trong {allowed}",
        )


def _get_employee_by_email(email: str) -> dict:
    """
    Query bảng employees theo email.
    Raises HTTPException 403 nếu không tìm thấy.
    """
    clean_email = email.strip().lower()
    print(f"DEBUG: get_employee_by_email: '{clean_email}'")

    supabase = get_supabase()
    result = (
        supabase.table("employees")
        .select("id, email, full_name, vai_tro, department, employee_code, onboarding_status")
        .eq("email", clean_email)
        .limit(1)
        .execute()
    )

    print(f"DEBUG: Employees query result: {result.data}")

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản '{clean_email}' không có trong hệ thống nhân sự. "
                   "Vui lòng liên hệ HR để được thêm vào hệ thống.",
        )

    emp = result.data[0]

    # === CHECK: No blocking by vai_tro or onboarding_status ===
    print(f"DEBUG: Employee found: name='{emp['full_name']}', vai_tro='{emp['vai_tro']}', "
          f"dept='{emp['department']}', "
          f"status='{emp.get('onboarding_status', 'N/A')}'")

    return emp


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Email domain không hợp lệ hoặc không có trong hệ thống"},
        401: {"model": ErrorResponse, "description": "Sai email hoặc mật khẩu"},
    },
    summary="Đăng nhập",
    description="""
Đăng nhập bằng email công ty và mật khẩu.

**Quy trình bảo mật:**
1. Validate email domain (chỉ chấp nhận @company.com)
2. Xác thực qua Supabase Auth
3. Kiểm tra email tồn tại trong bảng employees
4. Trả về JWT token kèm thông tin vai_tro (role)

**Swagger UI:** Sau khi nhận token, nhấn nút 🔒 Authorize ở trên và dán token vào.
""",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint — tương thích OAuth2PasswordRequestForm để
    Swagger UI có thể gọi trực tiếp qua nút Authorize.

    form_data.username = email
    form_data.password = password
    """
    email = form_data.username.strip().lower()
    password = form_data.password

    print(f"\n{'='*60}")
    print(f"DEBUG LOGIN: email='{email}', password_len={len(password)}")
    print(f"{'='*60}")

    # Step 1: Validate email domain
    _validate_email_domain(email)

    # Step 2: Authenticate via Supabase Auth
    print(f"DEBUG: Calling Supabase sign_in_with_password...")
    try:
        supabase = get_supabase()
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        print(f"DEBUG: Supabase auth SUCCESS - user={auth_response.user.email}")
    except Exception as e:
        print(f"DEBUG: Supabase auth EXCEPTION: type={type(e).__name__}, msg={e}")
        error_msg = str(e).lower()
        if "invalid" in error_msg or "credential" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Email hoặc mật khẩu không đúng (Supabase: {e})",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.error(f"Supabase auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống xác thực: {e}",
        )

    if not auth_response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 3: Check employee exists in our database
    supabase_email = auth_response.user.email
    employee = _get_employee_by_email(supabase_email)

    # Step 4: Build response
    session = auth_response.session
    user_info = UserInfo(
        id=employee["id"],
        email=employee["email"],
        full_name=employee["full_name"],
        vai_tro=employee["vai_tro"],
        department=employee["department"],
        employee_code=employee.get("employee_code"),
    )

    return TokenResponse(
        access_token=session.access_token,
        token_type="bearer",
        expires_at=session.expires_at,
        user=user_info,
    )


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Thông tin user hiện tại",
    description="Trả về thông tin của user đang đăng nhập. Yêu cầu Bearer token.",
)
async def get_me(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """Trả về thông tin user từ JWT token."""
    return current_user
