"""
Pydantic schemas cho Auth module.
Dùng chung cho request/response validation và Swagger UI documentation.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ───


class LoginRequest(BaseModel):
    """Schema cho request đăng nhập."""
    email: EmailStr = Field(..., examples=["nguyen.van.a@company.com"])
    password: str = Field(..., min_length=6, examples=["securepassword123"])


# ─── Response Schemas ───


class UserInfo(BaseModel):
    """Thông tin user trả về sau khi đăng nhập."""
    id: str = Field(..., description="UUID of employee in database")
    email: str
    full_name: str
    vai_tro: str = Field(..., description="Role: nhan_vien_moi | quan_ly | hr_admin | it_admin")
    department: str
    employee_code: str | None = None


class TokenResponse(BaseModel):
    """Response trả về khi đăng nhập thành công."""
    access_token: str = Field(..., description="JWT access token from Supabase")
    token_type: str = Field(default="bearer")
    expires_at: int = Field(..., description="Unix timestamp khi token hết hạn")
    user: UserInfo


class ErrorResponse(BaseModel):
    """Schema cho error response."""
    detail: str
    error_code: str | None = None


class HelloResponse(BaseModel):
    """Response cho protected Hello World endpoint."""
    message: str
    user: UserInfo
    timestamp: datetime = Field(default_factory=datetime.now)
