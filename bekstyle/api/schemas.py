from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


def format_som(val: int | None) -> str:
    if val is None:
        return ""
    return f"{val:,}".replace(",", " ") + " so'm"


class CategoryOut(BaseModel):
    id: int
    name: str
    emoji: str
    sort_order: int
    product_count: int = 0


class ProductOut(BaseModel):
    id: int
    title: str
    name: Optional[str] = None
    description: str
    price: int
    formatted_price: str
    old_price: Optional[int] = None
    formatted_old_price: Optional[str] = None
    discount_percent: Optional[int] = None
    category_id: int
    category_name: str = ""
    photos: List[str]
    colors: List[str]
    sizes: List[str]
    in_stock: bool
    is_new: bool
    is_hit: bool
    views: int = 0


class CartItemAdd(BaseModel):
    product_id: int
    color: Optional[str] = None
    size: Optional[str] = None
    qty: int = 1


class CartItemUpdate(BaseModel):
    qty: int


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    product_price: int
    formatted_price: str
    product_photo: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    qty: int
    item_total: int
    formatted_item_total: str


class CartSummaryOut(BaseModel):
    items: List[CartItemOut]
    total_items: int
    subtotal: int
    formatted_subtotal: str
    grand_total: int
    formatted_grand_total: str


class OrderItemIn(BaseModel):
    product_id: int
    title: str
    price: int
    color: Optional[str] = None
    size: Optional[str] = None
    qty: int = 1
    photo: Optional[str] = None


class OrderCreate(BaseModel):
    customer_name: str
    phone: str
    city: str = ""
    address: str
    customer_username: Optional[str] = None
    items: Optional[List[OrderItemIn]] = None


class OrderOut(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_username: Optional[str] = None
    phone: str
    city: str = ""
    address: str
    items: List[Dict[str, Any]] if False else Any
    total: int
    formatted_total: str
    status: str
    status_label: str
    created_at: datetime


class UserProfileOut(BaseModel):
    telegram_id: int
    name: str
    username: Optional[str] = None
    phone: Optional[str] = None
    balance: int
    formatted_balance: str
    orders_count: int = 0
    is_admin: bool = False


class SettingsOut(BaseModel):
    contact_username: str
    yuan_rate: int
    markup_percent: int
    delivery_text: str
    channel_username: str
