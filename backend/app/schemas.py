from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

Role = Literal["student", "mentor"]


class CaptchaAnswer(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=1, max_length=32)


class CaptchaChallengeOut(BaseModel):
    challenge_id: str
    image_data_uri: str
    expires_in: int


class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Role
    captcha: CaptchaAnswer


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320, description="Email or username")
    password: str = Field(min_length=1, max_length=128)
    captcha: CaptchaAnswer


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    role: Role
    is_admin: bool
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class ResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    description: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    description: str
    tags: list[str]
    created_at: datetime


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: Role
    phone: str = Field(default="", max_length=32)
    organisation: str = Field(default="", max_length=160)
    newsletter_opt_in: bool = False
    source: str = Field(default="website", max_length=64)
    captcha: CaptchaAnswer


class LeadAccepted(BaseModel):
    status: Literal["registered"] = "registered"
    message: str


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    phone: str
    organisation: str
    source: str
    newsletter_opt_in: bool
    status: str
    invited_at: datetime | None
    activated_at: datetime | None
    created_at: datetime


class LeadList(BaseModel):
    total: int
    limit: int
    offset: int
    counts: dict[str, int]
    items: list[LeadOut]


class InviteRequest(BaseModel):
    """Target specific leads by id, or every lead still in `new` status."""

    lead_ids: list[int] = Field(default_factory=list, max_length=500)
    all_new: bool = False
    resend: bool = False


class InviteResult(BaseModel):
    sent: int
    skipped: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class InviteCheck(BaseModel):
    valid: bool
    name: str | None = None
    email: EmailStr | None = None
    role: Role | None = None
    reason: str | None = None


class ActivateRequest(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class NewsletterSend(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body_markdown: str = Field(min_length=1, max_length=100_000)
    audience: Literal["all", "student", "mentor"] = "all"
    test_to: EmailStr | None = Field(
        default=None, description="Send a single preview to this address instead of the list"
    )


class NewsletterResult(BaseModel):
    subject: str
    audience: str
    recipient_count: int
    failed_count: int
    test: bool = False


class SearchResults(BaseModel):
    query: str
    total: int
    limit: int
    offset: int
    items: list[ResourceOut]
