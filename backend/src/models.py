from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InteractionType(Enum):
    POSITIVE_VIEW = "positive_view"
    NEGATIVE_VIEW = "negative_view"
    CART = "cart"
    PURCHASE = "purchase"
    RATE = "rate"


class Product(BaseModel):
    item_id: str
    product_name: str
    category: str
    about_product: Optional[str]
    img_link: Optional[str]
    discount_percentage: Optional[float]
    discounted_price: Optional[float]
    actual_price: float
    product_link: Optional[str]
    rating_count: Optional[int]
    rating: Optional[float]


class User(BaseModel):
    user_id: str
    email: str
    age: int
    gender: str
    signup_date: date
    preferences: str
    user_preferences: Optional[List["CategoryTree"]] = None
    views: Optional[List["Product"]] = None  # quotes avoid circular import issues

    model_config = ConfigDict(from_attributes=True)


class ProductReview(BaseModel):
    id: int
    productId: str
    userId: Optional[str] = None
    userName: Optional[str] = None  # User's email/name for display
    rating: int
    title: Optional[str] = ""
    comment: Optional[str] = ""
    created_at: datetime


class ReviewSummary(BaseModel):
    productId: str
    count: int
    avg_rating: float


class ReviewSummarization(BaseModel):
    productId: str
    summary: str


class ProductReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = ""
    comment: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class SignUpRequest(BaseModel):
    email: str
    password: str
    display_name: str = Field(min_length=2, max_length=50, description="Display name for public use (required)")
    age: int = Field(gt=0, description="Age must be positive")
    gender: str


class PreferencesRequest(BaseModel):
    category_ids: List[str]


class AuthResponse(BaseModel):
    user: User
    token: str


class CartItem(BaseModel):
    user_id: str
    product_id: str
    quantity: int


class CheckoutRequest(BaseModel):
    user_id: str
    items: List[CartItem]
    shipping_address: str
    payment_method: str


class Order(BaseModel):
    order_id: int
    user_id: str
    items: List[CartItem]
    total_amount: float
    order_date: datetime
    status: str


class CategoryTree(BaseModel):
    category_id: str
    name: str
    subcategories: List['CategoryTree'] = []

    model_config = ConfigDict(from_attributes=True)


# Onboarding models
class OnboardingProductsResponse(BaseModel):
    products: List[Product]
    round_number: int
    total_interactions: int
    is_complete: bool
    max_rounds: int = 3
    target_interactions: int = 10


class OnboardingSelectionRequest(BaseModel):
    selected_product_ids: List[str]
    round_number: int


class OnboardingSelectionResponse(BaseModel):
    interactions_logged: int
    total_interactions: int
    round_number: int
    is_complete: bool
    next_round_available: bool
    max_rounds: int = 3
    target_interactions: int = 10


# This is needed for the forward reference in CategoryTree
CategoryTree.model_rebuild()
