from pydantic import BaseModel, Field


class TestProvisionRequest(BaseModel):
    telegram_id: int = Field(gt=0)

    duration_minutes: int = Field(
        default=20,
        ge=5,
        le=1440,
    )




class CreateOrderRequest(BaseModel):
    plan_code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
