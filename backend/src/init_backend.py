"""
This script is used for initilizing the backend database.
This should be run by a job once per cluster.
"""

import asyncio
import json
import logging
import os
import random
import re
import subprocess
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.db import get_engine
from database.fetch_feast_users import seed_users
from database.models_sql import Base, Category, Product, Review, User


# Simple, description-aware review generators per rating
def _generate_review_title(product_name: str, rating: int, keyword: str | None = None) -> str:
    sentiments = {
        5: ["Outstanding", "Absolutely love it", "Perfect", "Fantastic find"],
        4: ["Great value", "Very good", "Impressive", "Solid choice"],
        3: ["It's okay", "Average", "Decent overall", "Meets expectations"],
        2: ["Not great", "Disappointing", "Needs improvement", "Below expectations"],
        1: ["Very poor", "Do not recommend", "Awful", "Big letdown"],
    }
    # Always return only the sentiment prefix to avoid noisy or repetitive keywords
    return random.choice(sentiments[rating])


def _extract_keywords(text_value: str, max_keywords: int = 5) -> list[str]:
    if not text_value:
        return []
    text_value = text_value.lower()
    words = re.split(r"[^a-z0-9]+", text_value)
    stopwords = {
        "with",
        "from",
        "this",
        "that",
        "your",
        "their",
        "about",
        "into",
        "over",
        "under",
        "have",
        "has",
        "had",
        "been",
        "will",
        "would",
        "could",
        "should",
        "and",
        "the",
        "for",
        "you",
        "our",
        "are",
        "was",
        "were",
        "they",
        "them",
        "can",
        "more",
        "than",
        "less",
        "inch",
        "inches",
        "cm",
        "mm",
        "made",
        "make",
        "makes",
        "use",
        "used",
        "using",
    }
    candidates = [w for w in words if len(w) >= 4 and w not in stopwords]
    counts = Counter(candidates)
    # Preserve order by frequency, then alphabetically to stabilize
    sorted_words = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in sorted_words[:max_keywords]]


def _generate_review_content(name: str, description: str, category_name: str, rating: int) -> str:
    desc_snippet = (description or "").strip()
    if len(desc_snippet) > 180:
        desc_snippet = desc_snippet[:180].rsplit(" ", 1)[0] + "..."

    keywords = _extract_keywords(description, max_keywords=6)
    # Prefer domain-y aspects when present in description
    default_aspects = [
        "battery life",
        "display",
        "comfort",
        "sound quality",
        "fit",
        "durability",
        "features",
        "price",
        "performance",
        "design",
    ]
    # Map common keywords to nicer aspect phrases
    keyword_to_aspect = {
        "battery": "battery life",
        "screen": "display",
        "display": "display",
        "bluetooth": "Bluetooth connectivity",
        "wireless": "wireless performance",
        "noise": "noise cancellation",
        "waterproof": "water resistance",
        "charging": "charging speed",
        "charger": "charging experience",
        "comfort": "overall comfort",
        "audio": "sound quality",
        "sound": "sound quality",
        "camera": "camera quality",
        "storage": "storage capacity",
        "speed": "overall speed",
        "durable": "durability",
        "design": "design and finish",
        "fit": "fit and ergonomics",
    }
    keyword_aspects = [keyword_to_aspect.get(k, k) for k in keywords]
    aspects_pool = (
        keyword_aspects + default_aspects + [category_name.lower() if category_name else ""]
    )
    aspects_pool = [a for a in aspects_pool if a]
    picked_aspects = (
        random.sample(aspects_pool, k=min(2, len(aspects_pool))) if aspects_pool else ["features"]
    )

    use_cases = [
        "daily use",
        "travel",
        "workouts",
        "office",
        "gaming",
        "commute",
        "home setup",
        "study",
    ]
    use_case = random.choice(use_cases)

    if rating >= 5:
        body_templates = [
            "{name} excels in {a1} and {a2}.",
            "Top-notch {a1}; also impressed by its {a2}.",
            "Build quality stands out and it shines for {use_case}.",
            "Superb {a1} with outstanding {a2}.",
            "Delivers consistently excellent {a1} and {a2}.",
            "A premium feel with stellar {a1}; great for {use_case}.",
            "Exceeds expectations in both {a1} and {a2}.",
            "Remarkably refined {a1}; {a2} is equally impressive.",
            "Polished experience for {use_case}; {a1} truly shines.",
            "One of the best for {use_case} thanks to {a1} and {a2}.",
        ]
        closing = "Highly recommended."
    elif rating == 4:
        body_templates = [
            "Strong {a1} with respectable {a2}.",
            "Great for {use_case}; minor nitpicks aside, it performs well.",
            "Good balance of {a1} and {a2} for the price.",
            "Solid {a1}; {a2} is better than expected.",
            "Very capable for {use_case} with reliable {a1}.",
            "Quality build and dependable {a2} overall.",
            "A well-rounded choice—{a1} and {a2} hold up.",
            "Pleasantly surprised by its {a1} during {use_case}.",
            "Performs admirably with only small trade-offs.",
            "Delivers on {a1}; {a2} is nearly great.",
        ]
        closing = "Would buy again."
    elif rating == 3:
        body_templates = [
            "Decent {a1}; {a2} could be better.",
            "Works for {use_case} but expect some compromises.",
            "Average overall—does the job.",
            "Usable {a1}; {a2} feels middling.",
            "Fine for {use_case}, not exceptional.",
            "Mixed results: okay {a1}, uneven {a2}.",
            "Competent enough if your focus is {a1}.",
            "Serviceable performance with a few rough edges.",
            "Balances {a1} and {a2} without standing out.",
            "Meets the basics, especially for {use_case}.",
        ]
        closing = "Meets expectations."
    elif rating == 2:
        body_templates = [
            "Underwhelming {a1} and inconsistent {a2}.",
            "Okay for {use_case}, but shortcomings are noticeable.",
            "Needs improvement in a few key areas.",
            "{a1} is weak; {a2} lacks refinement.",
            "Not ideal for {use_case}; issues get in the way.",
            "Frequent hiccups with {a1} and {a2}.",
            "Falls short of expectations despite some promise.",
            "Usable in a pinch, but rough around the edges.",
            "Compromises in {a1} make it hard to recommend.",
            "Subpar showing for {use_case} overall.",
        ]
        closing = "Not my first choice."
    else:
        body_templates = [
            "Disappointing {a1} and poor {a2}.",
            "Not ideal for {use_case}; issues outweigh benefits.",
            "Fell short in day-to-day use.",
            "Serious drawbacks in {a1} and {a2}.",
            "Struggles with {use_case}; difficult to use.",
            "Unreliable {a2}; {a1} is also lacking.",
            "Frustrating experience overall, especially for {use_case}.",
            "Significant flaws overshadow any strengths.",
            "Regrettable {a1}; {a2} is worse.",
            "Hard to recommend given the persistent issues.",
        ]
        closing = "Would not recommend."

    a1 = picked_aspects[0]
    a2 = picked_aspects[1] if len(picked_aspects) > 1 else picked_aspects[0]
    body = random.choice(body_templates).format(name=name, a1=a1, a2=a2, use_case=use_case)

    if desc_snippet:
        return f"{body} Based on the details: {desc_snippet} {closing}"
    return f"{body} {closing}"


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _use_llm_for_reviews() -> bool:
    return os.getenv("USE_LLM_FOR_REVIEWS", "false").lower() in ("1", "true", "yes")


async def _generate_reviews_with_llm(
    name: str,
    description: str,
    category_name: str,
    num_reviews: int,
    allowed_ratings: list[int],
    required_ratings: list[int] | None = None,
) -> list[dict]:
    """
    Ask an OpenAI-compatible LLM to generate review JSON objects.
    Returns list of dicts with keys: rating(int), title(str), comment(str).
    """
    api_base = os.getenv("LLM_API_BASE")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "llama-3.1-8b-instruct")
    timeout_s = float(os.getenv("LLM_TIMEOUT", "30"))
    min_words = int(os.getenv("LLM_COMMENT_MIN_WORDS", "60"))
    max_words = int(os.getenv("LLM_COMMENT_MAX_WORDS", "120"))

    if not api_base or not api_key:
        raise RuntimeError(
            "LLM_API_BASE and LLM_API_KEY must be set when USE_LLM_FOR_REVIEWS is enabled"
        )

    sys_prompt = (
        "You write succinct, realistic e-commerce reviews."
        " Respond ONLY with JSON matching the schema."
    )
    constraints = [
        f"Generate exactly {num_reviews} reviews.",
        f"Allowed ratings: {sorted(set(allowed_ratings))}.",
        "Titles <= 6 words; do not include product or brand names.",
        f"Comments {min_words}-{max_words} words; reference relevant aspects "
        f"from the description.",
    ]
    if required_ratings:
        constraints.append(
            f"Ensure at least one review for each of: {sorted(set(required_ratings))}."
        )
    user_prompt = (
        "Generate product reviews as JSON.\n"
        f"Name: {name}\n"
        f"Category: {category_name}\n"
        f"Description: {description[:800]}\n"
        "Constraints:\n- " + "\n- ".join(constraints) + "\n"
        'Return JSON: {"reviews":[{"rating":1..5,"title":"...","comment":"..."}, ...]}'
    )

    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    logger.info(
        f"[LLM] Calling chat/completions model={model} base={api_base} "
        f"num={num_reviews} allowed={allowed_ratings} required={required_ratings}"
    )
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        obj = json.loads(content)
        reviews = obj.get("reviews", [])
    logger.info(f"[LLM] Received {len(reviews)} raw reviews from model")

    results: list[dict] = []
    for r in reviews:
        try:
            rating = int(r.get("rating"))
            title = str(r.get("title", "")).strip()
            comment = str(r.get("comment", "")).strip()
        except Exception:
            continue
        if rating not in allowed_ratings:
            continue
        if not title or not comment:
            continue
        if len(title.split()) > 12:
            title = " ".join(title.split()[:12])
        # Allow more verbose comments
        if len(comment) > 1500:
            comment = comment[:1500]
        results.append({"rating": rating, "title": title, "comment": comment})

    return results[:num_reviews]


def _get_reviews_cache_path() -> str:
    return os.getenv("REVIEWS_CACHE_PATH", "/app/backend/src/reviews_cache.json")


async def _load_reviews_from_cache(session: AsyncSession) -> int:
    """
    Load reviews from a JSON cache file if it exists. Returns number of reviews inserted.
    Expected JSON structure:
     {"products": [{"item_id": str, "reviews": [{"rating": int, "title": str,
      "comment": str}, ...]}]}
    """
    cache_path = _get_reviews_cache_path()
    try:
        exists = os.path.exists(cache_path)
    except Exception:
        exists = False
    logger.info(f"[Reviews] Cache path={cache_path} exists={exists}")
    if not os.path.exists(cache_path):
        return 0

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        logger.info(f"[Reviews] Cache file loaded: products_count={len(products)}")

        # Validate product ids exist to avoid FK errors
        rows = (await session.execute(select(Product.item_id))).all()
        valid_ids = {row[0] for row in rows}
        logger.info(f"[Reviews] DB valid product_ids={len(valid_ids)}")

        # Get all available user IDs for assignment
        user_result = await session.execute(select(User.user_id))
        available_user_ids = [row[0] for row in user_result.fetchall()]

        if not available_user_ids:
            logger.error("❌ No users found for cache review assignment")
            return 0

        to_insert: list[Review] = []
        total_processed = 0
        total_skipped = 0

        for prod in products:
            item_id = prod.get("item_id")
            if not item_id or item_id not in valid_ids:
                logger.warning(f"[Reviews] Skipping cached reviews for unknown item_id={item_id}")
                continue

            # Check existing reviews for this product to avoid duplicates
            existing_reviews = (
                await session.execute(
                    select(Review.rating, Review.title, Review.content).where(
                        Review.item_id == item_id
                    )
                )
            ).all()
            existing_set = {
                (r.rating, r.title or None, r.content or None) for r in existing_reviews
            }

            # Get users who haven't reviewed this product yet
            existing_reviewers = await session.execute(
                select(Review.user_id).where(Review.item_id == item_id)
            )
            used_user_ids = {row[0] for row in existing_reviewers.fetchall() if row[0] is not None}
            available_users_for_product = [
                uid for uid in available_user_ids if uid not in used_user_ids
            ]

            product_skipped = 0
            product_added = 0

            for r in prod.get("reviews", []):
                rating = r.get("rating")
                title = (r.get("title") or "").strip() or None
                comment = (r.get("comment") or "").strip() or None
                total_processed += 1

                if not isinstance(rating, int) or rating < 1 or rating > 5:
                    total_skipped += 1
                    product_skipped += 1
                    continue

                # Check if this review already exists
                review_key = (rating, title, comment)
                if review_key in existing_set:
                    logger.debug(
                        f"[Reviews] Skipping duplicate review for item_id={item_id} "
                        f"rating={rating} title='{title}'"
                    )
                    total_skipped += 1
                    product_skipped += 1
                    continue

                # Assign user ID for this review
                if not available_users_for_product:
                    logger.warning(
                        f"[Reviews] No available users for product {item_id}, using random user"
                    )
                    assigned_user_id = random.choice(available_user_ids)
                else:
                    assigned_user_id = available_users_for_product.pop(0)

                to_insert.append(
                    Review(
                        item_id=item_id,
                        user_id=assigned_user_id,
                        rating=rating,
                        title=title,
                        content=comment,
                    )
                )
                # Add to existing set to avoid duplicates within the same batch
                existing_set.add(review_key)
                product_added += 1

            if product_added > 0 or product_skipped > 0:
                logger.info(
                    f"[Reviews] Product {item_id}: added={product_added},"
                    f" skipped={product_skipped}"
                )

        if to_insert:
            logger.info(f"[Reviews] Preparing to insert cached reviews count={len(to_insert)}")
            session.add_all(to_insert)
            await session.commit()
            logger.info(
                f"Loaded {len(to_insert)} reviews from cache file: {cache_path} "
                f"(processed={total_processed}, skipped={total_skipped})"
            )
            return len(to_insert)
        else:
            logger.info(
                f"[Reviews] No new reviews to insert from cache "
                f"(processed={total_processed}, skipped={total_skipped})"
            )
        return 0
    except Exception as ex:
        await session.rollback()
        logger.warning(f"Failed to load reviews from cache {cache_path}: {ex}")
        return 0


def _write_reviews_cache(cache_records: list[dict]) -> None:
    """
    Write the generated reviews to a JSON cache file for reuse.
    cache_records:
     [{"item_id": str, "reviews": [{"rating": int, "title": str, "comment": str}, ...]}, ...]
    """
    cache_path = _get_reviews_cache_path()
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"products": cache_records}, f, ensure_ascii=False, indent=2)
        logger.info(
            f"Wrote reviews cache file with {len(cache_records)} products to: {cache_path}"
        )
    except Exception as ex:
        logger.warning(f"Failed to write reviews cache to {cache_path}: {ex}")


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
        raw_items_file = (
            "../../recommendation-core/src/recommendation_core/feature_repo/data/"
            "recommendation_items.parquet"
        )

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
            WHERE cp.category_id NOT IN (
                SELECT parent_id FROM category WHERE parent_id IS NOT NULL
            )
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
        raw_categories_file = (
            "../../recommendation-core/src/recommendation_core/feature_repo/data/"
            "category_relationships.parquet"
        )

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


async def populate_reviews(
    min_reviews_per_product: int = 5,
    max_reviews_per_product: int = 10,
    skip_if_exists: bool = True,
):
    """
    Generate synthetic, description-aware reviews for each product.
    Ensures ratings range from 1..5 are represented per product, with 5-10 total reviews by
    default.
    Each review is associated with a unique user (one review per user per product).
    If skip_if_exists is True and no reviews exist at all, generate; otherwise, top-up per product to
    minimum and fill missing ratings.
    """  # noqa: E501
    if min_reviews_per_product < 5:
        min_reviews_per_product = 5
    if max_reviews_per_product < min_reviews_per_product:
        max_reviews_per_product = min_reviews_per_product

    engine = get_engine()
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        # Get all available user IDs for review assignment
        user_result = await session.execute(select(User.user_id))
        available_user_ids = [row[0] for row in user_result.fetchall()]

        if not available_user_ids:
            logger.error("❌ No users found in database. Cannot create reviews without users.")
            raise RuntimeError("No users available for review assignment. Run seed_users() first.")

        logger.info(
            f"[Reviews] Found {len(available_user_ids)} users available for review assignment"
        )

        # Helper function to get available users for a product (users who haven't reviewed it yet)
        async def get_available_users_for_product(item_id: str) -> list[str]:
            """Get list of user IDs who haven't reviewed this product yet."""
            existing_reviewers = await session.execute(
                select(Review.user_id).where(Review.item_id == item_id)
            )
            used_user_ids = {row[0] for row in existing_reviewers.fetchall() if row[0] is not None}
            return [uid for uid in available_user_ids if uid not in used_user_ids]

        # Helper function to assign user ID for a new review
        def assign_user_for_review(item_id: str, available_users_for_product: list[str]) -> str:
            """Assign a user ID for a new review, ensuring one review per user per product."""
            if not available_users_for_product:
                logger.warning(
                    f"[Reviews] No available users for product {item_id}, reusing users"
                )
                # If no users available, randomly pick from all users
                # (this shouldn't happen with 150 users)
                return random.choice(available_user_ids)
            return available_users_for_product.pop(0)  # Remove user from available list

        # Log LLM-related env
        logger.info(
            f"[Reviews] USE_LLM_FOR_REVIEWS={_use_llm_for_reviews()} "
            f"model={os.getenv('LLM_MODEL')} base={os.getenv('LLM_API_BASE')} "
            f"timeout={os.getenv('LLM_TIMEOUT')}"
        )
        # If table is completely empty, we'll do a full generation pass
        total_existing = (await session.execute(select(func.count(Review.id)))).scalar_one()
        table_empty = (total_existing or 0) == 0
        logger.info(f"[Reviews] Table empty={table_empty} existing_count={total_existing}")
        if skip_if_exists and not table_empty:
            logger.info(
                "ℹ️ Reviews table has data; will top-up per product to minimum and "
                "ensure coverage."
            )

        # If table empty, try loading from JSON cache first
        if table_empty:
            loaded = await _load_reviews_from_cache(session)
            logger.info(f"[Reviews] Attempted cache load, loaded_count={loaded}")
            if loaded > 0:
                # If we successfully loaded, we can return early
                return

        # Load products joined with their category names
        products_rows = (
            await session.execute(
                select(
                    Product.item_id,
                    Product.name,
                    Product.description,
                    Category.name,
                ).join(Category, Product.category_id == Category.category_id)
            )
        ).all()

        # Choose a small subset of products to be "positive-only" (4/5-star reviews only)
        total_products = len(products_rows)
        if total_products > 0:
            positive_k = random.randint(5, min(10, total_products))
            positive_item_ids = set(random.sample([row[0] for row in products_rows], k=positive_k))
        else:
            positive_item_ids = set()
        logger.info(f"[Reviews] Selected {len(positive_item_ids)} positive-only products")

        # Choose a disjoint subset of products to be "negative-only" (1/2-star reviews only)
        remaining_item_ids = [row[0] for row in products_rows if row[0] not in positive_item_ids]
        if len(remaining_item_ids) > 0:
            negative_k = random.randint(5, min(10, len(remaining_item_ids)))
            negative_item_ids = set(random.sample(remaining_item_ids, k=negative_k))
        else:
            negative_item_ids = set()
        logger.info(f"[Reviews] Selected {len(negative_item_ids)} negative-only products")

        to_add: list[Review] = []
        cache_records: list[dict] = []
        any_llm_used = False
        for item_id, name, description, category_name in products_rows:
            # Get available users for this product (users who haven't reviewed it yet)
            available_users_for_product = await get_available_users_for_product(item_id)
            logger.debug(
                f"[Reviews] Product {item_id}: {len(available_users_for_product)}"
                "users available for reviews"
            )

            is_positive_only = item_id in positive_item_ids
            is_negative_only = item_id in negative_item_ids
            new_reviews_for_product: list[dict] = []

            if is_positive_only:
                # Remove existing negative reviews (<=3 stars) for positive-only products
                await session.execute(
                    delete(Review).where((Review.item_id == item_id) & (Review.rating <= 3))
                )
                # Count existing positive reviews
                existing_rows = (
                    await session.execute(
                        select(Review.id, Review.rating).where(
                            (Review.item_id == item_id) & (Review.rating >= 4)
                        )
                    )
                ).all()
                current_count = len(existing_rows)
                present_ratings = {row.rating for row in existing_rows}
                # Ensure at least one 4 and one 5 when possible
                missing_ratings = [r for r in [4, 5] if r not in present_ratings]

                target_total = max(min_reviews_per_product, current_count)
                target_total = min(target_total, max_reviews_per_product)
                needed = max(target_total - current_count, 0)

                # If table is empty, allow variety within bounds
                if table_empty and current_count == 0:
                    target_total = random.randint(min_reviews_per_product, max_reviews_per_product)
                    needed = target_total
                    # Ensure both 4 and 5 appear at least once
                    missing_ratings = [4, 5]

                used_llm = False
                allowed = [4, 5]
                try:
                    if _use_llm_for_reviews() and (needed > 0):
                        llm_reviews = await _generate_reviews_with_llm(
                            name,
                            description or "",
                            category_name or "",
                            needed,
                            allowed_ratings=allowed,
                            required_ratings=missing_ratings,
                        )
                        if llm_reviews:
                            for r in llm_reviews:
                                logger.info(
                                    f"[LLM] product={item_id} name={name} rating={r.get('rating')}"
                                    f" title={r.get('title')} comment={r.get('comment')}"
                                )
                            for r in llm_reviews:
                                to_add.append(
                                    Review(
                                        item_id=item_id,
                                        user_id=assign_user_for_review(
                                            item_id, available_users_for_product
                                        ),
                                        rating=r["rating"],
                                        title=r["title"],
                                        content=r["comment"],
                                    )
                                )
                                new_reviews_for_product.append(r)
                            used_llm = True
                            any_llm_used = True
                except Exception as ex:
                    logger.warning(
                        f"LLM review generation failed for positive-only product {item_id}: {ex}"
                    )

                if not used_llm:
                    # Add must-have positives first
                    for rating in missing_ratings[
                        : max(0, max_reviews_per_product - current_count)
                    ]:
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )

                    remaining_slots = max(
                        0,
                        min(
                            max_reviews_per_product - current_count - len(missing_ratings),
                            needed - len(missing_ratings),
                        ),
                    )
                    for _ in range(remaining_slots):
                        rating = random.choice(allowed)
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )
                logger.info(
                    f"[Reviews] product={item_id} name={name} mode=positive-only "
                    f"used={'LLM' if used_llm else 'PY'} "
                    f"newly_added={len(new_reviews_for_product)}"
                )
            elif is_negative_only:
                # Remove existing positive reviews (>=4 stars) for negative-only products
                await session.execute(
                    delete(Review).where((Review.item_id == item_id) & (Review.rating >= 4))
                )
                # Count existing negative reviews
                existing_rows = (
                    await session.execute(
                        select(Review.id, Review.rating).where(
                            (Review.item_id == item_id) & (Review.rating <= 2)
                        )
                    )
                ).all()
                current_count = len(existing_rows)
                present_ratings = {row.rating for row in existing_rows}
                # Ensure at least one 1 and one 2 when possible
                missing_ratings = [r for r in [1, 2] if r not in present_ratings]

                target_total = max(min_reviews_per_product, current_count)
                target_total = min(target_total, max_reviews_per_product)
                needed = max(target_total - current_count, 0)

                if table_empty and current_count == 0:
                    target_total = random.randint(min_reviews_per_product, max_reviews_per_product)
                    needed = target_total
                    missing_ratings = [1, 2]

                used_llm = False
                allowed = [1, 2]
                try:
                    if _use_llm_for_reviews() and (needed > 0):
                        llm_reviews = await _generate_reviews_with_llm(
                            name,
                            description or "",
                            category_name or "",
                            needed,
                            allowed_ratings=allowed,
                            required_ratings=missing_ratings,
                        )
                        if llm_reviews:
                            for r in llm_reviews:
                                logger.info(
                                    f"[LLM] product={item_id} name={name} rating={r.get('rating')}"
                                    f" title={r.get('title')} comment={r.get('comment')}"
                                )
                            for r in llm_reviews:
                                to_add.append(
                                    Review(
                                        item_id=item_id,
                                        user_id=assign_user_for_review(
                                            item_id, available_users_for_product
                                        ),
                                        rating=r["rating"],
                                        title=r["title"],
                                        content=r["comment"],
                                    )
                                )
                                new_reviews_for_product.append(r)
                            used_llm = True
                            any_llm_used = True
                except Exception as ex:
                    logger.warning(
                        f"LLM review generation failed for negative-only product {item_id}: {ex}"
                    )

                if not used_llm:
                    # Add must-have negatives first
                    for rating in missing_ratings[
                        : max(0, max_reviews_per_product - current_count)
                    ]:
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )

                    remaining_slots = max(
                        0,
                        min(
                            max_reviews_per_product - current_count - len(missing_ratings),
                            needed - len(missing_ratings),
                        ),
                    )
                    for _ in range(remaining_slots):
                        rating = random.choice(allowed)
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )
                logger.info(
                    f"[Reviews] product={item_id} name={name} mode=negative-only "
                    f"used={'LLM' if used_llm else 'PY'} "
                    f"newly_added={len(new_reviews_for_product)}"
                )
            else:
                # Current reviews for this product (all ratings)
                existing_rows = (
                    await session.execute(
                        select(Review.id, Review.rating).where(Review.item_id == item_id)
                    )
                ).all()
                current_count = len(existing_rows)
                present_ratings = {row.rating for row in existing_rows}
                missing_ratings = [r for r in [1, 2, 3, 4, 5] if r not in present_ratings]

                target_total = max(min_reviews_per_product, current_count)
                target_total = min(target_total, max_reviews_per_product)
                needed = max(target_total - current_count, 0)

                if table_empty and current_count == 0:
                    target_total = random.randint(min_reviews_per_product, max_reviews_per_product)
                    needed = target_total
                    missing_ratings = [1, 2, 3, 4, 5]

                used_llm = False
                allowed = [1, 2, 3, 4, 5]
                try:
                    if _use_llm_for_reviews() and (needed > 0):
                        llm_reviews = await _generate_reviews_with_llm(
                            name,
                            description or "",
                            category_name or "",
                            needed,
                            allowed_ratings=allowed,
                            required_ratings=missing_ratings,
                        )
                        if llm_reviews:
                            for r in llm_reviews:
                                logger.info(
                                    f"[LLM] product={item_id} name={name} rating={r.get('rating')}"
                                    f" title={r.get('title')} comment={r.get('comment')}"
                                )
                            for r in llm_reviews:
                                to_add.append(
                                    Review(
                                        item_id=item_id,
                                        user_id=assign_user_for_review(
                                            item_id, available_users_for_product
                                        ),
                                        rating=r["rating"],
                                        title=r["title"],
                                        content=r["comment"],
                                    )
                                )
                                new_reviews_for_product.append(r)
                            used_llm = True
                            any_llm_used = True
                except Exception as ex:
                    logger.warning(f"LLM review generation failed for product {item_id}: {ex}")

                if not used_llm:
                    for rating in missing_ratings[
                        : max(0, max_reviews_per_product - current_count)
                    ]:
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )

                    remaining_slots = max(
                        0,
                        min(
                            max_reviews_per_product - current_count - len(missing_ratings),
                            needed - len(missing_ratings),
                        ),
                    )
                    for _ in range(remaining_slots):
                        rating = random.randint(1, 5)
                        title = _generate_review_title(
                            name, rating, (_extract_keywords(description, 1) or [None])[0]
                        )
                        content = _generate_review_content(
                            name, description or "", category_name or "", rating
                        )
                        to_add.append(
                            Review(
                                item_id=item_id,
                                user_id=assign_user_for_review(
                                    item_id, available_users_for_product
                                ),
                                rating=rating,
                                title=title,
                                content=content,
                            )
                        )
                        new_reviews_for_product.append(
                            {"rating": rating, "title": title, "comment": content}
                        )
                logger.info(
                    f"[Reviews] product={item_id} name={name} mode=mixed "
                    f"used={'LLM' if used_llm else 'PY'} "
                    f"newly_added={len(new_reviews_for_product)}"
                )

            # Track per-product records for JSON cache
            if new_reviews_for_product:
                cache_records.append({"item_id": item_id, "reviews": new_reviews_for_product})

        if to_add:
            total_new = len(to_add)
            session.add_all(to_add)
            await session.commit()
            logger.info(
                f"[Reviews] Created {total_new} reviews across {len(products_rows)} products "
                f"(top-up mode={not table_empty})."
            )
            # If we used the LLM for any product and table was empty, write cache for future reuse
            if any_llm_used and table_empty and cache_records:
                cache_obj = {"products": cache_records}
                try:
                    logger.info("[Reviews] LLM_CACHE_JSON_START")
                    logger.info(json.dumps(cache_obj, ensure_ascii=False, indent=2))
                    logger.info("[Reviews] LLM_CACHE_JSON_END")
                except Exception as ex:
                    logger.warning(f"[Reviews] Failed to log LLM cache JSON: {ex}")
                _write_reviews_cache(cache_records)
        else:
            logger.info("[Reviews] Already satisfied minimums/coverage; nothing to create.")


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
        await populate_reviews()
        logger.info("✅ Reviews populated successfully")
    except Exception as e:
        logger.error(f"❌ Error during database initialization: {e}")
        logger.info("🔄 Keeping pod alive for debugging...")
        # Keep the pod running for debugging
        subprocess.run(["tail", "-f", "/dev/null"])


if __name__ == "__main__":
    asyncio.run(setup_all())
