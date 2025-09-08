import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from database.models_sql import Review
from models import ProductReview, ReviewSummary, ProductReviewCreate
from routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["reviews"])


@router.get("/{product_id}/reviews", response_model=List[ProductReview])
async def get_reviews_for_product(
    product_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = (
            select(
                Review.id,
                Review.item_id,
                Review.user_id,
                Review.rating,
                Review.title,
                Review.content,
                Review.created_at,
            )
            .where(Review.item_id == product_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await db.execute(stmt)).all()
        return [
            ProductReview(
                id=row.id,
                productId=row.item_id,
                userId=row.user_id,
                rating=row.rating,
                title=row.title or "",
                comment=row.content or "",
                created_at=row.created_at,
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching reviews for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch reviews")


@router.get("/{product_id}/reviews/summary", response_model=ReviewSummary)
async def get_reviews_summary(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(func.count(Review.id), func.avg(Review.rating)).where(
            Review.item_id == product_id
        )
        count, avg_rating = (await db.execute(stmt)).one_or_none() or (0, None)
        return ReviewSummary(
            productId=product_id, count=count or 0, avg_rating=float(avg_rating or 0.0)
        )
    except Exception as e:
        logger.error(f"Error computing review summary for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute review summary")


@router.post(
    "/{product_id}/reviews", response_model=ProductReview, status_code=status.HTTP_201_CREATED
)
async def create_review_for_product(
    product_id: str,
    payload: ProductReviewCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        review = Review(
            item_id=product_id,
            user_id=user.user_id,
            rating=payload.rating,
            title=(payload.title or "").strip() or None,
            content=(payload.comment or "").strip() or None,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)

        return ProductReview(
            id=review.id,
            productId=review.item_id,
            userId=review.user_id,
            rating=review.rating,
            title=review.title or "",
            comment=review.content or "",
            created_at=review.created_at,
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating review for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create review")
