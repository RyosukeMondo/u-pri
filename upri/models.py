from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(min_length=1, max_length=150)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str):
            if any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("Control characters are not allowed")
            try:
                value.encode("cp932")
            except UnicodeEncodeError:
                raise ValueError("Text must be representable in CP932")
        return value


class Address(StrictModel):
    name: Text
    postal_code: Annotated[str, StringConstraints(pattern=r"^[0-9]{7}$")]
    address1: Text
    address2: str = Field(default="", max_length=50)
    address3: str = Field(default="", max_length=50)
    phone: Annotated[str, StringConstraints(pattern=r"^[0-9][0-9-]{8,19}$")]

    @field_validator("phone")
    @classmethod
    def phone_digits(cls, value):
        if not 9 <= len(value.replace("-", "")) <= 15:
            raise ValueError("Phone must contain 9 to 15 digits")
        return value


class Item(StrictModel):
    name: Text
    quantity: int = Field(default=1, ge=1, le=999, strict=True)


class Shipment(StrictModel):
    # A deliberately narrow, ordinary prepaid Yu-Pack profile. Unsupported services
    # cannot silently fall back to a different product.
    reference: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,19}$")]
    ship_date: date
    recipient: Address
    sender: Address
    items: list[Item] = Field(min_length=1, max_length=3)


class Batch(StrictModel):
    shipments: list[Shipment] = Field(min_length=1, max_length=100)

    @field_validator("shipments")
    @classmethod
    def unique_references(cls, value):
        if len({s.reference for s in value}) != len(value):
            raise ValueError("Duplicate shipment references")
        return value
