from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class Product(BaseModel):
    id: int
    sku: str
    name: str
    price_paise: int
    stock: int
    reorder_threshold: int
    category: str

class CatalogResponse(BaseModel):
    products: list[Product]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    agent_version: str = '1.0'

class CheckoutItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1)

class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]
    trigger_reason: str = 'manual_checkout'

    @field_validator('items')
    @classmethod
    def check_items_not_empty(cls, v):
        if not v:
            raise ValueError('Items list cannot be empty')
        return v

class CheckoutResponse(BaseModel):
    order_id: str
    amount_paise: int
    currency: str = 'INR'
    status: str
    receipt: str

class LedgerEntry(BaseModel):
    id: int | None = None
    timestamp: str
    trigger_reason: str
    skus: list[str]
    cart_value_paise: int
    razorpay_order_id: str | None = None
    status: str
    error_message: str | None = None

class ErrorResponse(BaseModel):
    error: str
    detail: str
    max_allowed_paise: int | None = None
    attempted_paise: int | None = None
