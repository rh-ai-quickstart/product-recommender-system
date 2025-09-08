from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc
from typing import List
import logging

from database.db import get_db
from database.models_sql import User, Category, Product as SQLProduct, StreamInteraction
from models import AuthResponse, PreferencesRequest, CategoryTree, Product
from models import User as UserResponse
from routes.auth import create_access_token, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# POST /users/preferences
@router.post(
    "/preferences",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
)
async def set_preferences(
    prefs: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Update DB
    user.preferences = prefs.preferences
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(
        user=UserResponse(
            user_id=user.user_id,
            email=user.email,
            age=user.age,
            gender=user.gender,
            signup_date=user.signup_date,
            preferences=user.preferences,
            views=[],
        ),
        token=create_access_token(subject=str(user.user_id)),  # Optional: refresh token
    )


# GET /users/preferences
@router.get(
    "/preferences",
    response_model=str,
    status_code=status.HTTP_200_OK,
)
async def get_preferences(user: User = Depends(get_current_user)):
    return user.preferences


# GET /users/categories
@router.get(
    "/categories",
    response_model=List[CategoryTree],
    status_code=status.HTTP_200_OK,
)
async def get_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all categories in a hierarchical tree structure."""
    # Get all categories in one query
    query = select(Category.category_id, Category.name, Category.parent_id)
    result = await db.execute(query)
    all_categories = result.all()

    # Build a dictionary for quick lookup
    category_dict = {str(cat.category_id): cat for cat in all_categories}

    def build_tree(parent_id=None):
        """Recursively build the category tree."""
        children = []
        for cat in all_categories:
            if str(cat.parent_id) == parent_id if parent_id else cat.parent_id is None:
                subcategories = build_tree(str(cat.category_id))
                children.append(CategoryTree(
                    category_id=str(cat.category_id),
                    name=cat.name,
                    subcategories=subcategories
                ))
        return children

    # Build and return the tree starting from root categories (parent_id is None)
    return build_tree()


# GET /users/categories/parents-only
@router.get(
    "/categories/parents-only",
    response_model=List[CategoryTree],
    status_code=status.HTTP_200_OK,
)
async def get_parent_categories_only(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get only parent categories (categories with no parent)."""
    # Query for parent categories only
    query = (
        select(Category.category_id, Category.name)
        .where(Category.parent_id.is_(None))
    )

    result = await db.execute(query)
    parent_categories = result.all()

    return [
        CategoryTree(
            category_id=str(cat.category_id),
            name=cat.name,
            subcategories=[]  # Empty array since we only want parents
        )
        for cat in parent_categories
    ]


# GET /users/categories/{category_id}/subcategories
@router.get(
    "/categories/{category_id}/subcategories",
    response_model=List[CategoryTree],
    status_code=status.HTTP_200_OK,
)
async def get_subcategories(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all subcategories for a given parent category."""
    # Query for subcategories with info about whether they have children
    query = (
        select(
            Category.category_id,
            Category.name,
            func.count(Category.sub_categories).label("child_count")
        )
        .where(Category.parent_id == category_id)
        .group_by(Category.category_id, Category.name)
    )

    result = await db.execute(query)
    subcategories = result.all()

    return [
        CategoryTree(
            category_id=str(subcat.category_id),
            name=subcat.name,
            subcategories=[]  # Empty for now, could be populated recursively if needed
        )
        for subcat in subcategories
    ]

@router.get(
    "/categories/{category_id}/top-products",
    response_model=List[Product],
    status_code=status.HTTP_200_OK,
)
async def get_top_products_in_category(
    category_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    include_subcategories: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get top products in a category ranked by interaction count."""

    try:
        # Verify category exists
        category_check = await db.execute(
            select(Category.category_id).where(Category.category_id == category_id)
        )
        if not category_check.first():
            raise HTTPException(status_code=404, detail="Category not found")

        # Build query based on whether to include subcategories
        if include_subcategories:
            # Use recursive CTE to get all subcategories
            query = text("""
                WITH RECURSIVE CategoryHierarchy AS (
                    SELECT category_id FROM category WHERE category_id = :category_id
                    UNION ALL
                    SELECT c.category_id
                    FROM category c
                    JOIN CategoryHierarchy ch ON c.parent_id = ch.category_id
                )
                SELECT
                    p.item_id,
                    p.name,
                    p.description,
                    p.actual_price,
                    p.discounted_price,
                    p.discount_percentage,
                    p.avg_rating,
                    p.num_ratings,
                    p.img_link,
                    p.product_link,
                    cat.name as category_name,
                    COALESCE(interaction_counts.interaction_count, 0) as interaction_count
                FROM products p
                JOIN CategoryHierarchy ch ON p.category_id = ch.category_id
                JOIN category cat ON p.category_id = cat.category_id
                LEFT JOIN (
                    SELECT
                        item_id,
                        COUNT(*) as interaction_count
                    FROM stream_interaction
                    GROUP BY item_id
                ) interaction_counts ON p.item_id = interaction_counts.item_id
                ORDER BY interaction_count DESC, p.avg_rating DESC
                LIMIT :limit
            """)
        else:
            # Single category query
            query = text("""
                SELECT
                    p.item_id,
                    p.name,
                    p.description,
                    p.actual_price,
                    p.discounted_price,
                    p.discount_percentage,
                    p.avg_rating,
                    p.num_ratings,
                    p.img_link,
                    p.product_link,
                    cat.name as category_name,
                    COALESCE(interaction_counts.interaction_count, 0) as interaction_count
                FROM products p
                JOIN category cat ON p.category_id = cat.category_id
                LEFT JOIN (
                    SELECT
                        item_id,
                        COUNT(*) as interaction_count
                    FROM stream_interaction
                    GROUP BY item_id
                ) interaction_counts ON p.item_id = interaction_counts.item_id
                WHERE p.category_id = :category_id
                ORDER BY interaction_count DESC, p.avg_rating DESC
                LIMIT :limit
            """)

        result = await db.execute(query, {
            "category_id": category_id,
            "limit": limit
        })

        products = result.fetchall()

        # Convert to Pydantic models
        return [
            Product(
                item_id=row.item_id,
                product_name=row.name,
                category=row.category_name,
                about_product=row.description,
                img_link=row.img_link,
                discount_percentage=row.discount_percentage,
                discounted_price=row.discounted_price,
                actual_price=row.actual_price,
                product_link=row.product_link,
                rating_count=row.num_ratings,
                rating=row.avg_rating,
            )
            for row in products
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching top products for category {category_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
