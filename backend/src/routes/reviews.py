import logging
import os
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from database.models_sql import Product, Review, User
from models import ProductReview, ProductReviewCreate, ReviewSummarization, ReviewSummary
from routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["reviews"])

MODEL_ENDPOINT = (
    os.getenv(
        "MODEL_ENDPOINT",
        "http://llama-3-1-8b-instruct-predictor-kickstart-llms.apps.ai-dev02.kni.syseng.devcluster.openshift.com/v1",  # noqa: E501
    )
    + "/chat/completions"
)

MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")


async def _check_product_exists(product_id: str, db: AsyncSession) -> None:
    """Check if a product exists, raise 404 if not found"""
    product_stmt = select(Product.item_id).where(Product.item_id == product_id)
    product_result = await db.execute(product_stmt)
    if not product_result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )


async def _fetch_reviews_from_db(
    product_id: str,
    db: AsyncSession,
    limit: int = 1000,
    offset: int = 0,
) -> List[ProductReview]:
    """Internal function to fetch reviews from database"""
    # First check if the product exists
    await _check_product_exists(product_id, db)

    stmt = (
        select(
            Review.id,
            Review.item_id,
            Review.user_id,
            Review.rating,
            Review.title,
            Review.content,
            Review.created_at,
            User.display_name.label("user_display_name"),
        )
        .outerjoin(User, Review.user_id == User.user_id)  # Left join to handle null user_ids
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
            userName=row.user_display_name if row.user_display_name else "Anonymous User",
            rating=row.rating,
            title=row.title or "",
            comment=row.content or "",
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/{product_id}/reviews", response_model=List[ProductReview])
async def get_reviews_for_product(
    product_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await _fetch_reviews_from_db(product_id, db, limit, offset)
    except Exception as e:
        logger.error(f"Error fetching reviews for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch reviews")


@router.get("/{product_id}/reviews/summary", response_model=ReviewSummary)
async def get_reviews_summary(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        # First check if the product exists
        await _check_product_exists(product_id, db)

        # Get review summary for the product
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


@router.get("/{product_id}/reviews/summarize", response_model=ReviewSummarization)
async def summarize_reviews(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        # Get all reviews for the product
        # TODO: Implement random sampling if too many reviews
        reviews = await _fetch_reviews_from_db(product_id, db, limit=1000)

        if not reviews:
            return ReviewSummarization(
                productId=product_id, summary="No reviews available for this product yet."
            )

        if len(reviews) < 4:
            return ReviewSummarization(
                productId=product_id,
                summary="Not enough reviews available for this product yet.",
            )

        # Stratified sampling by rating (1..5). We group reviews into buckets by
        # star rating, sort each bucket by recency (created_at desc), then allocate
        # a per-bucket quota proportionally with a minimum of 1 for any non-empty
        # bucket, and trim/redistribute to exactly SUMMARIZE_MAX_REVIEWS.
        # Example:
        #   - Total reviews = 10, target SUMMARIZE_MAX_REVIEWS = 6
        #   - Counts per rating = {1star:1, 2star:2, 3star:3, 4star:2, 5star:2}
        #   - Proportional quotas ≈ {1:1, 2:1, 3:2, 4:1, 5:1} (sum=6)
        #   - Take that many most recent from each bucket and concatenate (e.g., 5star→4star→3star→2star→1star)
        try:
            import math

            max_reviews = int(os.getenv("SUMMARIZE_MAX_REVIEWS", "200"))
            if max_reviews <= 0:
                max_reviews = 200

            sampled = reviews
            if len(reviews) > max_reviews:
                # Group by rating
                buckets = {r: [] for r in (1, 2, 3, 4, 5)}
                for r in reviews:
                    rating = int(getattr(r, "rating", 0) or 0)
                    if rating in buckets:
                        buckets[rating].append(r)
                # Sort each bucket by recency (created_at desc; fallback by id desc)
                for r in buckets:
                    buckets[r].sort(
                        key=lambda x: (
                            getattr(x, "created_at", None) is not None,
                            getattr(x, "created_at", None) or 0,
                            getattr(x, "id", 0) or 0,
                        ),
                        reverse=True,
                    )
                total = sum(len(buckets[r]) for r in buckets)
                # Initial proportional quotas
                quotas = {r: 0 for r in buckets}
                for r in buckets:
                    count = len(buckets[r])
                    if count > 0:
                        quotas[r] = max(1, int(round(max_reviews * count / total)))
                # Adjust quotas to sum exactly to max_reviews
                current = sum(quotas.values())
                # Reduce if over
                if current > max_reviews:
                    # Prefer reducing buckets with the largest quotas > 1
                    while current > max_reviews:
                        # Pick bucket with max quota (>1) and available items
                        r_max = max((rk for rk in quotas if quotas[rk] > 1), key=lambda k: quotas[k], default=None)
                        if r_max is None:
                            break
                        quotas[r_max] -= 1
                        current -= 1
                # Increase if under (and if bucket has remaining items)
                if current < max_reviews:
                    leftovers = max_reviews - current
                    # Distribute to buckets with the most remaining items
                    order = sorted(
                        buckets.keys(),
                        key=lambda k: (len(buckets[k]) - quotas[k]),
                        reverse=True,
                    )
                    i = 0
                    while leftovers > 0 and order:
                        k_r = order[i % len(order)]
                        if len(buckets[k_r]) > quotas[k_r]:
                            quotas[k_r] += 1
                            leftovers -= 1
                        i += 1
                        # break if no bucket has remaining
                        if all(len(buckets[k]) <= quotas[k] for k in buckets):
                            break
                # Build sampled set in rating order (optional)
                sampled = []
                for r in (5, 4, 3, 2, 1):
                    take = quotas.get(r, 0)
                    if take > 0 and buckets[r]:
                        sampled.extend(buckets[r][:take])
            else:
                sampled = reviews
        except Exception as e:
            logger.info(f"Stratified sampling skipped due to error: {e}")
            sampled = reviews

        # Prepare review text for summarization
        review_texts = []
        for review in sampled:
            review_text = f"Rating: {review.rating}/5"
            if review.title:
                review_text += f" - Title: {review.title}"
            if review.comment:
                review_text += f" - Comment: {review.comment}"
            review_texts.append(review_text)

        # Combine all reviews into a single text
        combined_reviews = "\n".join(review_texts)

        # Create prompt for Ollama
        prompt = f"""
Please analyze and summarize the following product reviews. Provide a concise summary that highlights:
1. Overall sentiment (positive, negative, mixed)
2. Key strengths mentioned by customers
3. Main concerns or issues raised
4. Overall recommendation

Reviews:
{combined_reviews}

Please provide a clear, concise summary include the adventage disadvantages and 2-3 sentences of conclusion:
"""  # noqa: E501

        response = requests.post(
            MODEL_ENDPOINT,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful, smart buyer who helps customers summarize reviews on electronic shops.",  # noqa: E501
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            headers={"Content-Type": "application/json"},
        )

        # Extract model response from JSON
        model_response = response.json()
        summary = model_response["choices"][0]["message"]["content"].strip()
        return ReviewSummarization(productId=product_id, summary=summary)

    except Exception as e:
        logger.error(f"Error summarizing reviews for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize reviews")
