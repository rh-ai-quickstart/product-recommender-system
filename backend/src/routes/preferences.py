from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc, delete
from typing import List
import logging
import uuid
import random

from database.db import get_db
from database.models_sql import User, Category, Product as SQLProduct, StreamInteraction, UserPreference
from services.database_service import db_service
from services.feast.feast_service import FeastService
from models import AuthResponse, PreferencesRequest, CategoryTree, Product, InteractionType
from models import OnboardingProductsResponse, OnboardingSelectionRequest, OnboardingSelectionResponse
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
    try:
        # === STEP 1: Validate category IDs exist ===
        if prefs.category_ids:
            # Verify all category IDs exist in database
            category_check = await db.execute(
                select(Category.category_id)
                .where(Category.category_id.in_([uuid.UUID(cid) for cid in prefs.category_ids]))
            )
            valid_categories = [str(cat.category_id) for cat in category_check.all()]

            if len(valid_categories) != len(prefs.category_ids):
                invalid_ids = set(prefs.category_ids) - set(valid_categories)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category IDs: {list(invalid_ids)}"
                )

        # === STEP 2: Clear existing UserPreference records ===
        await db.execute(
            delete(UserPreference).where(UserPreference.user_id == user.user_id)
        )

        # === STEP 3: Create new UserPreference records ===
        if prefs.category_ids:
            new_preferences = [
                UserPreference(
                    user_id=user.user_id,
                    category_id=uuid.UUID(category_id)
                )
                for category_id in prefs.category_ids
            ]
            db.add_all(new_preferences)

        # === STEP 4: Update legacy string field for backward compatibility ===
        if prefs.category_ids:
            # Get category names for legacy string field
            category_names_query = await db.execute(
                select(Category.name)
                .where(Category.category_id.in_([uuid.UUID(cid) for cid in prefs.category_ids]))
            )
            category_names = [cat.name for cat in category_names_query.all()]
            user.preferences = "|".join(category_names)
        else:
            user.preferences = ""

        # === STEP 5: Commit all changes ===
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # === STEP 6: Build user_preferences for response ===
        if prefs.category_ids:
            user_prefs_query = await db.execute(
                select(Category.category_id, Category.name, Category.parent_id)
                .join(UserPreference, UserPreference.category_id == Category.category_id)
                .where(UserPreference.user_id == user.user_id)
            )
            user_categories = user_prefs_query.all()

            user_preferences_response = [
                CategoryTree(
                    category_id=str(cat.category_id),
                    name=cat.name,
                    subcategories=[]
                )
                for cat in user_categories
            ]
        else:
            user_preferences_response = []

        return AuthResponse(
            user=UserResponse(
                user_id=user.user_id,
                email=user.email,
                age=user.age,
                gender=user.gender,
                signup_date=user.signup_date,
                preferences=user.preferences,
                user_preferences=user_preferences_response,
                views=[],
            ),
            token=create_access_token(subject=str(user.user_id)),
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error setting preferences for user {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save preferences")


# GET /users/preferences
@router.get(
    "/preferences",
    response_model=str,
    status_code=status.HTTP_200_OK,
)
async def get_preferences(user: User = Depends(get_current_user)):
    return user.user_preferences


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


# Helper function to get user's interaction count
async def _get_user_interaction_count(db: AsyncSession, user_id: str) -> int:
    """
    Get the total number of positive interactions for a user from the database.

    This function is used to:
    1. Check if user has already completed onboarding (>=10 interactions)
    2. Provide current interaction count in API responses
    3. Validate that new submissions don't exceed limits

    Args:
        db: Database session
        user_id: User's unique identifier

    Returns:
        int: Count of positive interactions, 0 if none found
    """
    query = select(func.count(StreamInteraction.id)).where(
        StreamInteraction.user_id == user_id,
        StreamInteraction.interaction_type == InteractionType.POSITIVE_VIEW.value
    )
    result = await db.execute(query)
    return result.scalar() or 0


# Helper function to get products from user's categories
async def _get_products_from_user_categories(
    db: AsyncSession, user: User, limit: int = 10
) -> List[Product]:
    """
    Fetch top products from user's selected categories for onboarding.

    Uses recursive CTE to include products from both selected categories and their subcategories.
    Products are ranked by interaction count (popularity) and rating.

    Args:
        db: Database session
        user: User object with category preferences
        limit: Maximum number of products to return (default: 10)

    Returns:
        List[Product]: Top products from user's categories, empty list if no categories selected
    """
    try:
        # Get user's category preferences
        user_categories_query = await db.execute(
            select(UserPreference.category_id).where(UserPreference.user_id == user.user_id)
        )
        category_ids = [str(cat.category_id) for cat in user_categories_query.all()]

        if not category_ids:
            # If no categories selected, return empty list
            return []

        # Use recursive CTE to get products from all selected categories and their subcategories
        query = text("""
            WITH RECURSIVE CategoryHierarchy AS (
                SELECT category_id FROM category WHERE category_id = ANY(:category_ids)
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

        result = await db.execute(query, {
            "category_ids": category_ids,
            "limit": limit
        })

        products = result.fetchall()

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

    except Exception as e:
        logger.error(f"Error fetching products from user categories: {e}")
        return []


# GET /users/onboarding/products
@router.get(
    "/onboarding/products",
    response_model=OnboardingProductsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_onboarding_products(
    round_number: int = Query(default=1, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get curated products for onboarding based on user's category preferences.
    Returns exactly 12 products: 10 from user's categories + 2 random products.
    """
    try:
        # Check current interaction count
        total_interactions = await _get_user_interaction_count(db, user.user_id)

        # Check if onboarding is already complete
        is_complete = total_interactions >= 10

        # Get products from user's categories (exactly 10)
        category_products = await _get_products_from_user_categories(db, user, limit=10)

        # Get random products from FeastService (exactly 2)
        feast_service = FeastService()
        random_products = feast_service._load_random_items(k=2)

        # Combine products - should be exactly 12 total
        all_products = category_products + random_products

        # Remove duplicates based on item_id while maintaining count
        seen_ids = set()
        unique_products = []
        for product in all_products:
            if product.item_id not in seen_ids:
                unique_products.append(product)
                seen_ids.add(product.item_id)

        # If we have fewer than 12 due to duplicates, get more random products
        if len(unique_products) < 12:
            additional_needed = 12 - len(unique_products)
            additional_random = feast_service._load_random_items(k=additional_needed * 2)  # Get extra to account for potential duplicates

            for product in additional_random:
                if product.item_id not in seen_ids and len(unique_products) < 12:
                    unique_products.append(product)
                    seen_ids.add(product.item_id)

        # Shuffle to randomize order
        random.shuffle(unique_products)

        # Ensure exactly 12 products (or as many as available)
        final_products = unique_products[:12]

        return OnboardingProductsResponse(
            products=final_products,
            round_number=round_number,
            total_interactions=total_interactions,
            is_complete=is_complete,
            max_rounds=3,
            target_interactions=10,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating onboarding products for user {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate onboarding products")


# POST /users/onboarding/selections
@router.post(
    "/onboarding/selections",
    response_model=OnboardingSelectionResponse,
    status_code=status.HTTP_200_OK,
)
async def save_onboarding_selections(
    selections: OnboardingSelectionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Save user's product selections as positive interactions for onboarding.
    """
    try:
        # Validate round number
        if selections.round_number < 1 or selections.round_number > 3:
            raise HTTPException(
                status_code=400,
                detail="Invalid round number. Must be between 1 and 3."
            )

        # Check current interaction count before adding new ones
        current_interactions = await _get_user_interaction_count(db, user.user_id)

        # Validate that we haven't exceeded limits
        if current_interactions >= 10:
            raise HTTPException(
                status_code=400,
                detail="Onboarding already completed with sufficient interactions"
            )

        # Validate product selections
        if not selections.selected_product_ids:
            raise HTTPException(
                status_code=400,
                detail="At least one product must be selected"
            )

        # Log interactions for each selected product
        interactions_logged = 0
        for product_id in selections.selected_product_ids:
            try:
                await db_service.log_interaction(
                    db=db,
                    user_id=user.user_id,
                    item_id=product_id,
                    interaction_type=InteractionType.POSITIVE_VIEW.value,
                )
                interactions_logged += 1
            except Exception as e:
                logger.error(f"Failed to log interaction for product {product_id}: {e}")
                # Continue with other products even if one fails

        # Get updated interaction count
        total_interactions = await _get_user_interaction_count(db, user.user_id)

        # Determine if onboarding is complete
        is_complete = total_interactions >= 10
        next_round_available = not is_complete and selections.round_number < 3

        return OnboardingSelectionResponse(
            interactions_logged=interactions_logged,
            total_interactions=total_interactions,
            round_number=selections.round_number,
            is_complete=is_complete,
            next_round_available=next_round_available,
            max_rounds=3,
            target_interactions=10,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving onboarding selections for user {user.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save onboarding selections")
