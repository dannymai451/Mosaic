"""Request validation for editable profile fields."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

Username = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=30,
        pattern=r"^[a-z0-9_]+$",
    ),
]


class ProfileTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: Literal["midnight", "paper", "plum"]


class ProfilePatch(BaseModel):
    """A partial owner update; fields omitted from the body remain unchanged."""

    model_config = ConfigDict(extra="forbid")

    username: Username | None = None
    display_name: str | None = None
    bio: str | None = None
    visibility: Literal["public", "private"] | None = None
    theme: ProfileTheme | None = None

    @field_validator(
        "username", "display_name", "bio", "visibility", "theme", mode="before"
    )
    @classmethod
    def reject_null_fields(cls, value):
        if value is None:
            raise ValueError("null is not allowed; omit the field to leave it unchanged")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display name must not be blank")
        if len(value) > 255:
            raise ValueError("display name must be at most 255 characters")
        return value

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: str) -> str:
        if len(value) > 500:
            raise ValueError("bio must be at most 500 characters")
        return value
