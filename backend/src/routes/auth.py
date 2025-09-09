import random
import string
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from database.models_sql import User, UserPreference, Category
from models import AuthResponse, LoginRequest, SignUpRequest, CategoryTree
from models import User as UserResponse
from services.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)

# OAuth2 scheme for Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def load_user_preferences(db: AsyncSession, user_id: str) -> list[CategoryTree]:
    """Helper function to load user preferences from UserPreference table"""
    user_prefs_query = await db.execute(
        select(Category.category_id, Category.name, Category.parent_id)
        .join(UserPreference, UserPreference.category_id == Category.category_id)
        .where(UserPreference.user_id == user_id)
    )
    user_categories = user_prefs_query.all()

    return [
        CategoryTree(
            category_id=str(cat.category_id),
            name=cat.name,
            subcategories=[]
        )
        for cat in user_categories
    ]


# Utility: generate a 27-digit user ID
def generate_user_id() -> str:
    return "".join(random.choices(string.digits, k=27))


# Dependency: get current user from JWT
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    payload: SignUpRequest,
    db: AsyncSession = Depends(get_db),
):
    # Prevent duplicates
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    # Create user with generated ID
    new_id = generate_user_id()
    user = User(
        user_id=new_id,
        email=payload.email,
        age=payload.age,
        gender=payload.gender,
        signup_date=date.today(),
        preferences="",
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Issue JWT
    token = create_access_token(subject=str(user.user_id))

    # Load user preferences from UserPreference table (new users will have empty preferences)
    user_preferences = await load_user_preferences(db, user.user_id)

    user_response = UserResponse(
        user_id=user.user_id,
        email=user.email,
        age=user.age,
        gender=user.gender,
        signup_date=user.signup_date,
        preferences=user.preferences,
        user_preferences=user_preferences,
        views=[],
    )
    return AuthResponse(user=user_response, token=token)


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    # Check credentials
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue JWT
    token = create_access_token(subject=str(user.user_id))

    # Load user preferences from UserPreference table
    user_preferences = await load_user_preferences(db, user.user_id)

    user_response = UserResponse(
        user_id=user.user_id,
        email=user.email,
        age=user.age,
        gender=user.gender,
        signup_date=user.signup_date,
        preferences=user.preferences,
        user_preferences=user_preferences,
        views=[],
    )
    return AuthResponse(user=user_response, token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user information"""
    # Load user preferences from UserPreference table
    user_preferences = await load_user_preferences(db, current_user.user_id)

    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        age=current_user.age,
        gender=current_user.gender,
        signup_date=current_user.signup_date,
        preferences=current_user.preferences,
        user_preferences=user_preferences,
        views=[],
    )
