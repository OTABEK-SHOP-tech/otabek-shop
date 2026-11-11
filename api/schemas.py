from datetime import datetime
from typing import Annotated, List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, StringConstraints, field_validator


# ==================== PRODUCT SCHEMAS ====================
class ProductBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(default="", max_length=5000)
    price: int = Field(..., ge=0, le=1_000_000_000)
    old_price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    category: str = Field(..., min_length=1, max_length=100)
    photos: List[str] = Field(default_factory=list, max_length=15)
    sizes: List[str] = Field(default_factory=list, max_length=20)
    colors: List[str] = Field(default_factory=list, max_length=20)
    weight_grams: Optional[int] = Field(default=None, ge=0, le=100_000)
    in_stock: bool = True
    is_new: bool = False
    is_hit: bool = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    old_price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    photos: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    weight_grams: Optional[int] = Field(default=None, ge=0, le=100_000)
    in_stock: Optional[bool] = None
    is_new: Optional[bool] = None
    is_hit: Optional[bool] = None


class ProductOut(ProductBase):
    id: int
    views: int
    created_at: datetime
    formatted_price: str = ""
    formatted_old_price: Optional[str] = None
    cargo_estimate: int = 0
    formatted_cargo_estimate: str = ""

    model_config = ConfigDict(from_attributes=True)


# ==================== CATEGORY SCHEMAS ====================
class CategoryBase(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    emoji: str = Field(default="🌸", max_length=20)
    sort_order: int = Field(default=0)


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    product_count: int = 0
    model_config = ConfigDict(from_attributes=True)


# ==================== CART SCHEMAS ====================
class CartItemAdd(BaseModel):
    product_id: int
    size: Optional[str] = None
    color: Optional[str] = None
    qty: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    qty: int = Field(..., ge=1, le=99)


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    product_price: int
    product_photo: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    qty: int
    weight_grams: Optional[int] = None
    item_total: int
    formatted_item_total: str


class CartSummaryOut(BaseModel):
    items: List[CartItemOut]
    total_items: int
    subtotal: int
    formatted_subtotal: str
    estimated_cargo: int
    formatted_estimated_cargo: str
    grand_total: int
    formatted_grand_total: str


# ==================== ORDER SCHEMAS ====================
class OrderCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_username: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None  # If client provides snapshot, or default to current cart
    use_cashback: Optional[int] = Field(default=0, ge=0)


class OrderOut(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_username: Optional[str] = None
    items_snapshot: List[Dict[str, Any]]
    total: int
    formatted_total: str = ""
    estimated_cargo: int
    formatted_cargo: str = ""
    status: str  # new, accepted, cancelled
    cashback_used: int = 0
    formatted_cashback_used: str = ""
    cargo_stage: str = "china_warehouse"
    formatted_cargo_stage: str = ""
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserMeOut(BaseModel):
    telegram_id: int
    name: str
    username: Optional[str] = None
    cashback_balance: int = 0
    formatted_cashback_balance: str = ""
    max_order_cashback_percent: int = 20
    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|accepted|cancelled)$")


# ==================== WISHLIST SCHEMAS ====================
class WishlistToggle(BaseModel):
    product_id: int


class WishlistOut(BaseModel):
    product_id: int
    product: ProductOut


# ==================== REVIEW SCHEMAS ====================
class ReviewCreate(BaseModel):
    text: Optional[str] = Field(default="", max_length=2000)
    customer_name: str = Field(..., min_length=2, max_length=100)
    photos: List[str] = Field(default_factory=list, max_length=5)


class ReviewOut(BaseModel):
    id: int
    photos: List[str]
    text: Optional[str]
    customer_name: str
    approved: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== SETTINGS SCHEMAS ====================
class SettingsDict(BaseModel):
    cargo_rate: int = 12000
    delivery_days: str = "10–15 kun"
    delivery_scope: str = "O'zbekiston bo'ylab"
    payment_terms: str = "100% oldindan to'lov"
    location: str = "Toshkent"
    contact_username: str = "+998939029799"
    channel_url: str = "https://t.me/moonlight_chinese_shop"
    channel_id: str = ""
    welcome_text: str = "Moonlight Chinese Shop ga xush kelibsiz! 🌸"


# ==================== STATS SCHEMAS ====================
class AdminStatsOut(BaseModel):
    total_users: int
    new_users_this_week: int
    total_orders: int
    new_orders: int
    accepted_orders: int
    total_products: int
    in_stock_products: int
    top_viewed_products: List[ProductOut]
    most_wishlisted_products: List[Dict[str, Any]]
    orders_per_day: List[Dict[str, Any]]


# ==================== BROADCAST SCHEMAS ====================
class BroadcastCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    photo_url: Optional[str] = None


# ==================== CONTEST SCHEMAS ====================
PrizeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
# Places 4..7; the first three keep their own fields.
ExtraPrizes = Annotated[List[PrizeText], Field(max_length=4)]


class ContestCreate(BaseModel):
    prize_1: str = Field(..., min_length=1, max_length=255)
    prize_2: str = Field(..., min_length=1, max_length=255)
    prize_3: str = Field(..., min_length=1, max_length=255)
    extra_prizes: ExtraPrizes = Field(default_factory=list)
    ends_at: datetime
    photo_file_id: Optional[str] = None
    only_new_subscribers: bool = True


class ContestUpdatePrizes(BaseModel):
    prize_1: str = Field(..., min_length=1, max_length=255)
    prize_2: str = Field(..., min_length=1, max_length=255)
    prize_3: str = Field(..., min_length=1, max_length=255)
    extra_prizes: Optional[ExtraPrizes] = None  # None keeps places 4+ unchanged


class ContestExtend(BaseModel):
    additional_days: Optional[int] = Field(default=None, ge=1, le=60)
    new_ends_at: Optional[datetime] = None


class ContestOut(BaseModel):
    id: int
    prize_1: str
    prize_2: str
    prize_3: str
    prizes: List[str] = Field(default_factory=list)
    photo_file_id: Optional[str] = None
    channel_message_id: Optional[int] = None
    status: str
    only_new_subscribers: bool = True
    created_at: datetime
    ends_at: datetime
    formatted_ends_at: str = ""
    is_active: bool = False
    total_participants: int = 0
    total_confirmed_invites: int = 0
    channel_url: str = ""
    winners_snapshot: Optional[List[Dict[str, Any]]] = None
    total_subscribers_gained: int = 0

    model_config = ConfigDict(from_attributes=True)


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    name: str
    username: Optional[str] = None
    score: int
    last_confirmed_at: Optional[datetime] = None


class ContestInviteItem(BaseModel):
    id: int
    invitee_id: int
    name: str
    username: Optional[str] = None
    status: str  # pending, confirmed, revoked
    started_at: datetime
    confirmed_at: Optional[datetime] = None


class MyContestStatsOut(BaseModel):
    has_active_contest: bool
    contest: Optional[ContestOut] = None
    user_id: int
    invite_link: str
    score: int
    rank: Optional[int] = None
    next_rank_score: Optional[int] = None
    invites: List[ContestInviteItem] = Field(default_factory=list)


class DisqualifyPayload(BaseModel):
    user_id: int
    reason: str = Field(default="Suspicious referral activity", max_length=255)


class SuspiciousUserItem(BaseModel):
    referrer_id: int
    name: str
    username: Optional[str] = None
    total_invites: int
    confirmed_invites: int
    revoked_invites: int
    revoked_ratio: float


# ==================== CARGO TRACKING SCHEMAS ====================
class CargoTrackingCreate(BaseModel):
    tracking_code: str = Field(..., min_length=3, max_length=100)
    order_id: Optional[int] = None
    user_id: Optional[int] = None
    status: str = Field(default="registered", max_length=50)
    current_location: Optional[str] = Field(default="", max_length=255)
    status_description: Optional[str] = Field(default="", max_length=1000)
    weight_grams: Optional[int] = None


class CargoTrackingOut(BaseModel):
    id: int
    tracking_code: str
    order_id: Optional[int] = None
    user_id: Optional[int] = None
    status: str
    current_location: Optional[str] = ""
    status_description: Optional[str] = ""
    weight_grams: Optional[int] = None
    updated_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== PROMO CODE SCHEMAS ====================
class PromoCodeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    discount_percent: Optional[int] = Field(default=None, ge=1, le=100)
    discount_amount: Optional[int] = Field(default=None, ge=0)
    min_order_amount: int = Field(default=0, ge=0)
    max_uses: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True
    valid_until: Optional[datetime] = None


class PromoCodeOut(BaseModel):
    id: int
    code: str
    discount_percent: Optional[int] = None
    discount_amount: Optional[int] = None
    min_order_amount: int = 0
    max_uses: Optional[int] = None
    used_count: int = 0
    is_active: bool = True
    valid_from: datetime
    valid_until: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


