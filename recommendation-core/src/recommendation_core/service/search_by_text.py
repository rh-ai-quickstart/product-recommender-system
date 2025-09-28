import pandas as pd
import numpy as np
import torch
from feast import FeatureStore
from transformers import AutoModel, AutoTokenizer
import logging
import os
from sqlalchemy import create_engine, text
from collections import Counter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

class SearchService:
    def __init__(self, store: FeatureStore):
        self.store = store
        self.tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(EMBEDDING_MODEL)
        self.model.eval()

    def _get_item_ids(self) -> pd.DataFrame:
        return self._get_item_ids_from_db()

    def _get_item_ids_from_db(self) -> pd.DataFrame:
        """
        Extract all item IDs from the products table in the database.

        Returns:
            pd.DataFrame: DataFrame with 'item_id' column containing all product IDs
        """
        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.error("DATABASE_URL not set - cannot retrieve item IDs from database")
                raise ValueError("DATABASE_URL environment variable is required")

            engine = create_engine(database_url)

            with engine.connect() as connection:
                result = connection.execute(text("SELECT item_id FROM products"))
                item_ids = [row[0] for row in result.fetchall()]

            logger.info(f"Retrieved {len(item_ids)} item IDs from database")
            return pd.DataFrame({"item_id": item_ids})

        except Exception as e:
            logger.error(f"Failed to retrieve item IDs from database: {e}")
            raise e

    def _get_free_text_embeddings(self, text: str) -> torch.Tensor:
        encoded_input = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        with torch.inference_mode():
            model_output = self.model(**encoded_input)
            # CLS pooling
            batch_embeddings = model_output[0][:, 0]
            # Normalize
            batch_embeddings = torch.nn.functional.normalize(batch_embeddings, p=2, dim=1)
        return batch_embeddings

    def _calculate_similarity_scores(
        self, free_text_embeddings: torch.Tensor, items_embeddnigs: torch.Tensor
    ) -> torch.Tensor:
        assert free_text_embeddings.shape[-1] == items_embeddnigs.shape[-1], (
            "Incompatible embeddings length"
        )

        try:
            similarity_scores = torch.cosine_similarity(
                free_text_embeddings, items_embeddnigs, dim=-1
            )
        except Exception as e:
            logger.error(f"failed to calculate embeddings due to error:\n{e}")
            raise e

        logger.info(
            f"calculated cosine similarity scores between free text embeddings of shape: {free_text_embeddings.shape} \
            and items embeddings of shape: {items_embeddnigs.shape} \
            resulted in scores vector of shape: {similarity_scores.shape}"
        )

        return similarity_scores

    def _get_top_k_items(
        self, items_df: pd.DataFrame, scores: torch.Tensor, k: int = 5
    ) -> tuple:
        assert len(items_df) == len(scores), "Incompatible length of items and scores"

        # take max score for each item
        max_scores, _ = torch.max(scores, dim=-1)

        top_scores, top_indices = torch.topk(max_scores, k)

        logger.info(f"top scores: {top_scores}\ntop indices: {top_indices}")
        items = items_df.iloc[top_indices.tolist()]

        return items["item_id"], top_scores

    def search_by_text(self, text, k) -> pd.DataFrame:
        logger.info(f"search_by_text: query='{text}', k={k}")
        all_items_df = self._get_item_ids()

        logger.info(f"candidate items: {len(all_items_df)}; sample={all_items_df['item_id'].head(3).tolist()}")

        logger.info(f"all items df columns: {all_items_df.columns.tolist()}")

        # Extract embedding data
        about_product_embeddings_df = self.store.get_online_features(
            features=["item_textual_features_embed:about_product_embedding"],
            entity_rows=[{"item_id": item_id} for item_id in all_items_df["item_id"]],
        ).to_df()

        product_name_embeddings_df = self.store.get_online_features(
            features=["item_name_features_embed:product_name_embedding"],
            entity_rows=[{"item_id": item_id} for item_id in all_items_df["item_id"]],
        ).to_df()

        category_embeddings_df = self.store.get_online_features(
            features=["item_category_features_embed:category_embedding"],
            entity_rows=[{"item_id": item_id} for item_id in all_items_df["item_id"]],
        ).to_df()

        logger.info(
            f"retrieved columns about={list(about_product_embeddings_df.columns)}, name={list(product_name_embeddings_df.columns)}, category={list(category_embeddings_df.columns)}"
        )

        # Extract the embedding arrays from the DataFrame columns
        about_product_embeddings = about_product_embeddings_df["about_product_embedding"].values
        product_name_embeddings = product_name_embeddings_df["product_name_embedding"].values
        category_embeddings = category_embeddings_df["category_embedding"].values

        # Diagnostics: null/empty counts and sample entry types/lengths (no logic change)
        try:
            about_nulls = int(np.sum([(x is None) or (hasattr(x, "__len__") and len(x) == 0) for x in about_product_embeddings]))
            name_nulls = int(np.sum([(x is None) or (hasattr(x, "__len__") and len(x) == 0) for x in product_name_embeddings]))
            cat_nulls = int(np.sum([(x is None) or (hasattr(x, "__len__") and len(x) == 0) for x in category_embeddings]))
            logger.info(f"null/empty vectors -> about:{about_nulls} name:{name_nulls} category:{cat_nulls}")
        except Exception as e:
            logger.info(f"null/empty vector count failed: {e}")

        try:
            def _sample_summ(arr):
                out = []
                for x in arr[:3]:
                    try:
                        l = len(x)
                    except Exception:
                        l = "NA"
                    out.append(f"{type(x).__name__}:{l}")
                return out
            logger.info(f"sample entries -> about:{_sample_summ(about_product_embeddings)} name:{_sample_summ(product_name_embeddings)} category:{_sample_summ(category_embeddings)}")
        except Exception as e:
            logger.info(f"sample summary failed: {e}")
        
        logger.info(f"Try/except block completed")

        # Get the tensors
        try:
            about_product_tensor = torch.tensor(
                np.stack(about_product_embeddings), dtype=torch.float32
            )
        except Exception as e:
            logger.info(f"np.stack(about_product_embeddings) failed: {e}")
            raise
        try:
            product_name_tensor = torch.tensor(np.stack(product_name_embeddings), dtype=torch.float32)
        except Exception as e:
            logger.info(f"np.stack(product_name_embeddings) failed: {e}")
            raise

        logger.info(f"shape of about_product_tensor: {about_product_tensor.shape}")
        logger.info(f"shape of product_name_tensor: {product_name_tensor.shape}")

        items_embeddings = torch.stack(
            [about_product_tensor, product_name_tensor], dim=1
        )
        logger.info(f"textual features has embeddings tensor of shape: {items_embeddings.shape}")

        free_text_embeddings = self._get_free_text_embeddings(text)
        logger.info(f"embedded free text with shape of: {free_text_embeddings.shape}")

        similarity_scores = self._calculate_similarity_scores(
            free_text_embeddings, items_embeddings
        )
        logger.info(f"similarity scores tensor shape: {similarity_scores.shape}")

        top_items, top_scores = self._get_top_k_items(all_items_df, similarity_scores, k=k)
        logger.info(f"top items are:\n{top_items}")
        logger.info(f"top scores are:\n{top_scores}")
        
        ids = pd.DataFrame()
        ids["item_id"] = top_items
        ids["event_timestamp"] = pd.to_datetime("now", utc=True)

        item_service = self.store.get_feature_service("item_service")
        values = self.store.get_historical_features(
            entity_df=ids,
            features=item_service,
        ).to_df()
        logger.info(f"returned rows: {len(values)}")

        # Add similarity scores to the results for sorting
        values["similarity_score"] = top_scores.numpy()
        
        # Sort by similarity score (highest first) to ensure proper order
        values = values.sort_values("similarity_score", ascending=False)
        logger.info(f"results sorted by similarity score (highest first)")
        
        # Remove the similarity_score column from final output to keep it clean
        values = values.drop("similarity_score", axis=1)
        
        return values
