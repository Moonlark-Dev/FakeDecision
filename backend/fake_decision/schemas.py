from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)


class AdminLoginIn(LoginIn):
    pass


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class AccountPatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class KeyCreateIn(BaseModel):
    name: str = Field(default="Default key", max_length=80)


class AssignIn(BaseModel):
    operator_id: str | None = None


class AnswerIn(BaseModel):
    answers: dict[str, Any]


class DraftIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class RandomizeIn(BaseModel):
    question_ids: list[str] | None = None


class OperatorCreateIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    password: str
    models: list[str] = Field(default_factory=list)


class OperatorPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    disabled: bool | None = None
    password: str | None = None
    models: list[str] | None = None


class UserPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    disabled: bool | None = None
    password: str | None = None


class ModelCreateIn(BaseModel):
    name: str
    display_name: str = Field(min_length=1, max_length=80)
    protocol: Literal["systemone", "google", "both"] = "both"
    description: str = Field(default="", max_length=2000)
    context_window: int = Field(default=65536, ge=0, le=10_000_000)
    enabled: bool = True
    sort_order: int = Field(default=100, ge=0, le=100000)


class ModelPatchIn(BaseModel):
    name: str | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    protocol: Literal["systemone", "google", "both"] | None = None
    description: str | None = Field(default=None, max_length=2000)
    context_window: int | None = Field(default=None, ge=0, le=10_000_000)
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class SettingsIn(BaseModel):
    values: dict[str, Any]


class LogoUploadIn(BaseModel):
    filename: str = Field(default="", max_length=200)
    data: str = Field(min_length=1, max_length=3_000_000)


class PlaygroundIn(BaseModel):
    protocol: Literal["systemone", "google"] = "systemone"
    model: str
    input: Any
    questions: dict[str, Any]
    timeout_ms: int | None = Field(default=None, ge=1000, le=900000)


class ForceFillIn(BaseModel):
    question_ids: list[str] | None = None
    submit: bool = False
