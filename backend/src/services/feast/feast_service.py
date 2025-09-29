import json
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import List

import pandas as pd
import requests
import tabulate as tb
import torch
from feast import FeatureStore
from minio import Minio
from PIL import Image as PILImage
from recommendation_core.models.data_util import data_preproccess
from recommendation_core.models.entity_tower import EntityTower
from recommendation_core.service.clip_encoder import ClipEncoder
from recommendation_core.service.dataset_provider import LocalDatasetProvider
from recommendation_core.service.search_by_image import SearchByImageService
from recommendation_core.service.search_by_text import SearchService
from sqlalchemy import create_engine, text as sql_text
from models import Product, User

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
CLIP_MODEL_SIZE = 512


class FeastService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeastService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Use the correct feature repo path
            path = Path("/app/recommendation-core/src/recommendation_core/feature_repo")
            self.store = FeatureStore(str(path))
            self._initialized = True
            self.user_encoder = self._load_user_encoder()
            self.user_service = self.store.get_feature_service("user_service")
            self.dataset_provider = LocalDatasetProvider(
                self.store, data_dir="/app/backend/src/services/feast/data"
            )  # TODO: remove path when Feast is the issue
            logger.info("[Feast] Initializing ClipEncoder...")
            self.clip_encoder = ClipEncoder()
            logger.info("[Feast] ClipEncoder initialized.")
            logger.info("[Feast] Initializing SearchByImageService...")
            self.search_by_image_service = SearchByImageService(self.store, self.clip_encoder)
            logger.info("[Feast] SearchByImageService initialized.")

    def _load_model_version(self):
        """
        Retrieve the most recently updated model version from the database.
        """
        from sqlalchemy import create_engine, text

        database_url = os.getenv("DATABASE_URL")
        engine = create_engine(database_url)

        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT version FROM model_version ORDER BY updated_at DESC LIMIT 1")
            )
            version = result.fetchone()[0]
            return version

    def _load_user_encoder(self):
        """
        Download and load the user encoder model and its configuration from MinIO.
        """
        minio_client = Minio(
            endpoint=os.getenv("MINIO_HOST", "endpoint") + ":" + os.getenv("MINIO_PORT", "9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "access-key"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "secret-key"),
            secure=False,
        )
        model_version = self._load_model_version()
        bucket_name = "user-encoder"
        object_name = f"user-encoder-{model_version}.pth"
        configuration = f"user-encoder-config-{model_version}.json"

        minio_client.fget_object(bucket_name, object_name, "/tmp/user-encoder.pth")
        minio_client.fget_object(bucket_name, configuration, "/tmp/user-encoder-config.json")

        with open("/tmp/user-encoder-config.json", "r") as f:
            json_config = json.load(f)
        user_encoder = EntityTower(
            json_config["users_num_numerical"], json_config["users_num_categorical"]
        )
        user_encoder.load_state_dict(torch.load("/tmp/user-encoder.pth"))

        return user_encoder

    def get_all_existing_users(self) -> List[dict]:
        """
        Return all existing user feature rows from the dataset provider.
        """
        try:
            user_df = self.dataset_provider.user_df()
            logger.info("Fetched all users")
            return user_df
        except Exception as e:
            logger.error(f"Failed to fetch users from feature view: {e}")
            return []

    def load_items_existing_user(self, user_id: str) -> List[Product]:
        """
        Get top recommended items for an existing user based on their user_id.
        """
        suggested_item_ids = self.store.get_online_features(
            features=self.store.get_feature_service("user_top_k_items"),
            entity_rows=[{"user_id": user_id}],
        )
        top_item_ids = suggested_item_ids.to_df().iloc[0]["top_k_item_ids"]
        return self._item_ids_to_product_list(top_item_ids)

    def _load_random_items(self, k: int = 10):
        """
        This function is called when a user has no prefereces.
        It'll return a list of random k items from the dataset.
        """
        items_df = self.dataset_provider.item_df()
        item_ids = items_df["item_id"].sample(k).tolist()
        return self._item_ids_to_product_list(item_ids)

    def load_items_new_user(self, user: User, k: int = 10):
        """
        Generate recommendations for a new user by encoding their features
        and querying the feature store for top-k similar items.
        """

        if not user.preferences or user.preferences.strip() == "" or user.preferences is None:
            logger.info(f"User {user.user_id} has no preferences, returning random items")
            return self._load_random_items(k)

        logger.info(f"User {user.user_id} has preferences, returning recommendations")
        user_as_df = pd.DataFrame([user.model_dump()])
        self.user_encoder.eval()
        user_embed = self.user_encoder(**data_preproccess(user_as_df))[0]
        top_k = self.store.retrieve_online_documents(
            query=user_embed.tolist(), top_k=k, features=["item_embedding:item_id"]
        )
        logger.info(f"Retrieved documents from store: {top_k.to_df()}")
        top_item_ids = top_k.to_df()["item_id"].tolist()
        return self._item_ids_to_product_list(top_item_ids)

    def _item_ids_to_product_list(self, top_item_ids: pd.Series | List) -> List[Product]:
        """
        Given a list of item_ids, fetch and return full product details from the feature store.
        """
        suggested_item = self.store.get_online_features(
            features=self.store.get_feature_service("item_service"),
            entity_rows=[{"item_id": item_id} for item_id in top_item_ids],
        ).to_df()
        logger.info(suggested_item.columns)
        logger.info(tb.tabulate(suggested_item, headers="keys", tablefmt="grid"))
        suggested_item = [
            Product(
                item_id=row.item_id,
                product_name=row.product_name,
                category=row.category,
                about_product=getattr(row, "about_product", None),
                img_link=getattr(row, "img_link", None),
                discount_percentage=getattr(row, "discount_percentage", None),
                discounted_price=getattr(row, "discounted_price", None),
                actual_price=row.actual_price,
                product_link=getattr(row, "product_link", None),
                rating_count=getattr(row, "rating_count", None),
                rating=getattr(row, "rating", None),
            )
            for row in suggested_item.itertuples()
        ]
        return suggested_item

    def search_item_by_text(self, text: str, k=5):
        """
        Deterministic + semantic search:
        - Deterministic boosts: exact > prefix > substring (via SQL)
        - If deterministic buckets provide >= k unique IDs, return them
        - Else, fetch semantic candidates to fill remaining slots up to k
        """
        search_service = SearchService(self.store)

        # Deterministic name boosting via SQL (no category)
        def _norm(s: str) -> str:
            return "".join(ch.lower() for ch in (s or "") if ch.isalnum())

        qn = _norm(text)
        exact_ids: List[str] = []
        prefix_ids: List[str] = []
        contains_ids: List[str] = []
        try:
            from sqlalchemy import create_engine, text as sql_text

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                raise RuntimeError("DATABASE_URL not set")
            engine = create_engine(database_url)

            exact_limit = max(k, 20)
            prefix_limit = max(k * 3, 20)
            contains_limit = max(k * 3, 20)

            with engine.connect() as conn:
                def _query_item_ids(where_clause: str, params: dict, limit: int) -> List[str]:
                    rows = conn.execute(
                        sql_text(
                            f"""
                            SELECT item_id
                            FROM products
                            WHERE {where_clause}
                            LIMIT {limit}
                            """
                        ),
                        params,
                    ).fetchall()
                    return [str(r[0]) for r in rows]

                # Common normalized expression
                norm_expr = "regexp_replace(lower(name), '[^a-z0-9]', '', 'g')"

                # Exact match
                exact_ids = _query_item_ids(
                    f"{norm_expr} = :qn",
                    {"qn": qn},
                    exact_limit,
                )

                # Prefix match
                prefix_ids = _query_item_ids(
                    f"{norm_expr} LIKE :prefix",
                    {"prefix": f"{qn}%"},
                    prefix_limit,
                )

                # Contains match
                contains_ids = _query_item_ids(
                    f"{norm_expr} LIKE :contains",
                    {"contains": f"%{qn}%"},
                    contains_limit,
                )

            logger.info(
                f"name-boost exact:{len(exact_ids)} prefix:{len(prefix_ids)} contains:{len(contains_ids)}"
            )
        except Exception as e:
            logger.info(f"name boosting skipped: {e}")

        # Merge with priority and dedupe
        merged: List[str] = []
        seen = set()
        for bucket in (exact_ids, prefix_ids, contains_ids):
            for iid in bucket:
                if iid not in seen:
                    merged.append(iid)
                    seen.add(iid)

        # If we already have k or more, return immediately
        if len(merged) >= k:
            final_ids = merged[:k]
            logger.info(f"final merged ids (top {k}) without semantic: {final_ids}")
            return self._item_ids_to_product_list(final_ids)

        # Otherwise fetch semantic candidates to fill remaining slots
        remaining = k - len(merged)
        semantic_k = max(k, 50)
        try:
            semantic_df = search_service.search_by_text(text, semantic_k)
            semantic_ids = semantic_df["item_id"].astype(str).tolist() if not semantic_df.empty else []
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            semantic_ids = []

        for iid in semantic_ids:
            if iid not in seen:
                merged.append(iid)
                seen.add(iid)
            if len(merged) >= k:
                break

        final_ids = merged[:k]
        logger.info(f"final merged ids (top {k}) with semantic fill: {final_ids}")

        return self._item_ids_to_product_list(final_ids)

    def search_item_by_image_link(self, image_link: str, k=5):
        """
        Perform image-based product search using an image URL.
        Returns top-k similar items.
        """
        try:
            # Manually check if the image is reachable and decodable
            resp = requests.get(image_link, timeout=100)
            resp.raise_for_status()

            # Try decoding it to ensure it's a valid image
            img = PILImage.open(BytesIO(resp.content))
            img.verify()  # Raises if the image is corrupt

        except Exception as e:
            logger.error(f"[Validation] Could not fetch/validate image: {e}")
            raise ValueError("Invalid or unreachable image URL.")
        try:
            results_df = self.search_by_image_service.search_by_image_link(image_link, k)
            logger.info(f"Got {len(results_df)} results:")
            logger.info(tb.tabulate(results_df, headers="keys", tablefmt="grid"))
            top_item_ids = results_df["item_id"].tolist()
            return self._item_ids_to_product_list(top_item_ids)
        except Exception as e:
            logger.error(f"Error in search_item_by_image_link: {e}")
            raise ValueError("Failed to process image from URL.")

    def search_item_by_image_file(self, image: PILImage.Image, k=5):
        logger.info("[Feast] Starting search_item_by_image_file")
        try:
            results_df = self.search_by_image_service.search_by_image(image, k)
            logger.info("[Feast] search_by_image() completed")

            if results_df.empty or "item_id" not in results_df:
                raise ValueError("No valid item_id results returned from image search.")

            logger.info(f"Got {len(results_df)} results:")
            logger.info(tb.tabulate(results_df, headers="keys", tablefmt="grid"))
            top_item_ids = results_df["item_id"].tolist()
            return self._item_ids_to_product_list(top_item_ids)

        except Exception as e:
            logger.error(f"[SearchByImage Error] {e}")
            raise ValueError("Failed to process image.")

    def get_item_by_id(self, item_id: int) -> Product:
        """
        Retrieve a single item by its ID and return it as a Product
        """
        product_list = self._item_ids_to_product_list([item_id])
        if not product_list:
            raise ValueError(f"Item with ID {item_id} not found.")
        return product_list[0]
