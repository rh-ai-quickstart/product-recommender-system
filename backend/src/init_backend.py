"""
This script is used for initilizing the backend database.
This should be run by a job once per cluster.
"""

import asyncio
import logging
import subprocess
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.db import get_engine
from database.fetch_feast_users import seed_users
from database.models_sql import Base, Category, Product

logger = logging.getLogger(__name__)


@dataclass
class category_dc:
    category_id: uuid
    name: str
    parent_id: uuid


async def create_tables():
    try:
        async with get_engine().begin() as conn:
            # Drop existing tables (dev only)
            await conn.run_sync(Base.metadata.drop_all)
            # Create fresh schema with updated types
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise


async def populate_products():
    try:
        # Read parquet file containing categories in Category, Parent Category format
        raw_items_file = "../../recommendation-core/src/recommendation_core/feature_repo/data/recommendation_items.parquet"  # noqa: E501

        script_dir = Path(__file__).resolve().parent
        data_file_path = script_dir / raw_items_file

        df_items = pd.read_parquet(data_file_path)

        engine = get_engine()
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        # This RCTE creates a string path for every root category to its leaf category
        # It is used during product loading to ensure
        # each product lands in the correct leaf category
        # based on the category field in the parquet file
        # (e.g., Electronics|WearableTechnology|SmartWatches)
        # This is necessary since the category/sub category names are not unique
        # (in fact, the category table and this query generates category
        # paths that have no products, but this is ok for the purposes of
        # loading the products those spurious category paths are ignored)
        categoryPaths = """
            WITH RECURSIVE CategoryPaths AS (
            SELECT category_id, name, category_id AS leaf_id, name AS path
            FROM category
            WHERE parent_id IS NULL
            UNION ALL
            SELECT c.category_id, c.name, c.category_id AS leaf_id, p.path || '|' || c.name AS path
            FROM category AS c
            JOIN CategoryPaths AS p ON c.parent_id = p.category_id
            )
            SELECT path, leaf_id, c2.name
            FROM CategoryPaths cp join category c2 on cp.leaf_id = c2.category_id
            WHERE cp.category_id NOT IN (SELECT parent_id FROM category WHERE parent_id IS NOT NULL)
            ORDER BY path
            """  # noqa: E501

        async with SessionLocal() as session:
            categoryPathsResults = (await session.execute(text(categoryPaths))).all()
            path_to_leaf_category_id = {row.path: row.leaf_id for row in categoryPathsResults}
            for _, item in df_items.iterrows():
                category_id = path_to_leaf_category_id[item["category"]]
                item_id = item["item_id"]
                product_name = item["product_name"]
                discounted_price = item["discounted_price"]
                actual_price = item["actual_price"]
                discount_percentage = item["discount_percentage"]
                rating = item["rating"]
                rating_count = item["rating_count"]
                about_product = item["about_product"]
                arrival_date = item["arrival_date"]
                img_link = item["img_link"]
                product_link = item["product_link"]

                session.add(
                    Product(
                        item_id=item_id,
                        category_id=category_id,
                        name=product_name,
                        description=about_product,
                        actual_price=actual_price,
                        discounted_price=discounted_price,
                        avg_rating=rating,
                        num_ratings=rating_count,
                        arrival_date=arrival_date,
                        discount_percentage=discount_percentage,
                        img_link=img_link,
                        product_link=product_link,
                    )
                )

            await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error loading items in init_backend: {e}")
        raise


async def populate_categories():
    try:
        # Read parquet file containing categories in Category, Parent Category format
        raw_categories_file = "../../recommendation-core/src/recommendation_core/feature_repo/data/category_relationships.parquet"  # noqa: E501

        script_dir = Path(__file__).resolve().parent
        data_file_path = script_dir / raw_categories_file

        df = pd.read_parquet(data_file_path)

        engine = get_engine()
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        root_categories_df = df[df["Parent Category"].isnull()]
        root_categories = [
            category_dc(uuid.uuid4(), row["Category"], None)
            for _, row in root_categories_df.iterrows()
        ]
        q = deque(root_categories)

        async with SessionLocal() as session:
            while len(q):
                next_category = q.popleft()
                children_of_next_df = df[df["Parent Category"] == next_category.name]
                # Technically, this multi-phase path to load the category graph
                #  is not correct since the category names are not unique. We'd have to
                # match on the path from the root category to the leaf vs just the leaf's name.
                # For example, 'Cables' may appear as a subcategory in several category paths
                # (computers, electronics, etc.).
                children_of_next = [
                    category_dc(uuid.uuid4(), row["Category"], next_category.category_id)
                    for _, row in children_of_next_df.iterrows()
                ]
                q.extend(children_of_next)
                session.add(
                    Category(
                        category_id=next_category.category_id,
                        name=next_category.name,
                        parent_id=next_category.parent_id,
                    )
                )

            await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error loading categories in init_backend: {e}")
        raise


async def setup_all():
    try:
        logger.info("🔄 Starting database initialization...")
        await create_tables()
        logger.info("🔄 Seeding users...")
        await seed_users()
        logger.info("✅ Database initialization completed successfully")
        await populate_categories()
        logger.info("✅ Categories populated successfully")
        await populate_products()
        logger.info("✅ Products populated successfully")
    except Exception as e:
        logger.error(f"❌ Error during database initialization: {e}")
        logger.info("🔄 Keeping pod alive for debugging...")
        # Keep the pod running for debugging
        subprocess.run(["tail", "-f", "/dev/null"])


if __name__ == "__main__":
    asyncio.run(setup_all())
