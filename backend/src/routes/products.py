import logging
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel

try:
    from PIL.UnidentifiedImageError import UnidentifiedImageError
except ImportError:
    UnidentifiedImageError = Exception

from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from database.models_sql import Product as ProductSQL
from models import InteractionType, Product, ProductReview
from routes.auth import get_current_user  # to resolve JWT user
from services.database_service import db_service  # Use global instance
from services.feast.feast_service import FeastService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/products/search", response_model=List[Product])
async def search_products_by_text(query: str, k: int = 5):
    """
    Search products by text query
    """
    try:
        feast = FeastService()
        return feast.search_item_by_text(query, k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}", response_model=Product)
async def get_product(
    product_id: str, user_id=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get product details by ID
    """
    # Log view interaction to database (replaces Kafka)
    await db_service.log_interaction(
        db=db,
        user_id=user_id.user_id,
        item_id=product_id,
        interaction_type=InteractionType.POSITIVE_VIEW.value,
    )

    try:
        feast = FeastService()
        return feast.get_item_by_id(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/{product_id}/interactions/click", status_code=204)
async def record_product_click(
    product_id: str, user_id=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Records a product click interaction event
    """
    # Log click interaction to database (replaces Kafka)
    await db_service.log_interaction(
        db=db,
        user_id=user_id.user_id,
        item_id=product_id,
        interaction_type=InteractionType.POSITIVE_VIEW.value,
    )
    return


async def get_product_reviews(session: AsyncSession, product_id: str):
    product = await session.get(ProductSQL, product_id)
    if product is None:
        return []
    await session.refresh(product, attribute_names=["reviews"])
    return product.reviews


class ImageRecommendationRequest_link(BaseModel):
    image_url: str
    num_recommendations: int = 10


@router.post("/products/search/image-link", response_model=List[Product])
async def recommend_for_image_link(payload: ImageRecommendationRequest_link):
    assert payload.image_url is not None and payload.image_url != "", "image_url is required"
    assert (
        payload.num_recommendations is not None and payload.num_recommendations > 0
    ), "num_recommendations is required"

    try:
        logger.info(f"Recommendations for image link: {payload.image_url}")
        recommendations = FeastService().search_item_by_image_link(
            payload.image_url, k=payload.num_recommendations
        )
        return recommendations
    except ValueError as e:
        logger.error(f"Error getting recommendations for image link {payload.image_url}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recommendations for image link {payload.image_url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/search/image-file", response_model=List[Product])
async def recommend_for_image_file(
    image_file: UploadFile = File(...), num_recommendations: int = Form(10)
):
    assert image_file is not None and image_file != "", "image_file is required"
    assert (
        num_recommendations is not None and num_recommendations > 0
    ), "num_recommendations is required"
    logger.info(f"Recommendations for image file: {image_file.filename}")
    try:
        contents = await image_file.read()
        image = Image.open(BytesIO(contents))
        image.load()
    except Exception as e:
        logger.error(f"Error opening image file {image_file.filename}: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        recommendations = FeastService().search_item_by_image_file(image, k=num_recommendations)
        return recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations for image file {image_file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/reviews/all", response_model=List[ProductReview])
async def list_all_product_reviews(product_id: str, db: AsyncSession = Depends(get_db)):
    reviews = await get_product_reviews(db, product_id)
    return [
        ProductReview(
            id=r.id,
            productId=r.item_id,
            userId=r.user_id,
            userName=r.user.display_name if r.user and r.user.display_name else "Anonymous User",
            rating=r.rating,
            title=r.title or "",
            comment=r.content or "",
            created_at=r.created_at,
        )
        for r in reviews
    ]
