"""Allowlisted remix settings; clients cannot supply listening IDs or image URLs."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Shape = Literal["pumpkin", "ghost", "bat", "skull"]


class RemixStyle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    shape: Shape = "pumpkin"
    background_color: Color = "#15131c"
    frame_style: Literal["none", "line", "double", "mat"] = "line"
    frame_color: Color = "#efaa73"
    frame_width: int = Field(default=4, ge=1, le=24)
    corner_radius: int = Field(default=24, ge=0, le=48)
    photo_dim: int = Field(default=30, ge=0, le=80)
    photo_x: int = Field(default=50, ge=0, le=100)
    photo_y: int = Field(default=50, ge=0, le=100)


class RemixWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(default="October after dark", min_length=1, max_length=60)
    style: RemixStyle = Field(default_factory=RemixStyle)
