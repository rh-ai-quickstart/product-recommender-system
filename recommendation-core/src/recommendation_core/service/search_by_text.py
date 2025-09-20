import pandas as pd
import numpy as np
import torch
from feast import FeatureStore
from transformers import AutoModel, AutoTokenizer
import logging
import os
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_ITEM_IDS = [
    "B084531076",
    "B021643208",
    "B087822269",
    "B022225855",
    "B018910852",
    "B018351245",
    "B080790126",
    "B060676914",
    "B041556003",
    "B063509641",
    "B020688727",
    "B030154994",
    "B046940933",
    "B035836512",
    "B094776775",
    "B092972373",
    "B090908854",
    "B098121122",
    "B035146282",
    "B090074928",
    "B045966581",
    "B089594423",
    "B077812526",
    "B047003110",
    "B097929144",
    "B093463150",
    "B060831524",
    "B016202258",
    "B092932418",
    "B066761259",
    "B091447632",
    "B096131989",
    "B020971177",
    "B065098996",
    "B044780908",
    "B077800621",
    "B041970599",
    "B081240343",
    "B086176890",
    "B013875754",
    "B032564965",
    "B023143608",
    "B030515189",
    "B038172140",
    "B011524102",
    "B033468625",
    "B052942594",
    "B092058636",
    "B048499601",
    "B020760888",
    "B068075712",
    "B056571160",
    "B091242298",
    "B094445004",
    "B061195209",
    "B011514542",
    "B045383985",
    "B095561923",
    "B087960088",
    "B021377787",
    "B077511983",
    "B011132658",
    "B079475474",
    "B061900771",
    "B067195030",
    "B042073692",
    "B048965695",
    "B042735803",
    "B053497663",
    "B030353727",
    "B048710304",
    "B039221379",
    "B058548947",
    "B067884623",
    "B058123406",
    "B022866619",
    "B076777436",
    "B029659206",
    "B091576052",
    "B085134271",
    "B045943815",
    "B068438965",
    "B039536204",
    "B034455289",
    "B014409352",
    "B011308507",
    "B030606265",
    "B024150540",
    "B046286070",
    "B035955176",
    "B051478073",
    "B061756593",
    "B060277283",
    "B021950831",
    "B043523310",
    "B044932801",
    "B088981711",
    "B020856760",
    "B048090551",
    "B063175588",
    "B041073264",
]


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

        logger.debug(
            f"calculated cosine similarity scores between free text embeddings of shape: {free_text_embeddings.shape} \
            and items embeddings of shape: {items_embeddnigs.shape} \
            resulted in scores vector of shape: {similarity_scores.shape}"
        )

        return similarity_scores

    def _get_top_k_items(
        self, items_df: pd.DataFrame, scores: torch.Tensor, k: int = 5
    ) -> pd.Series:
        assert len(items_df) == len(scores), "Incompatible length of items and scores"

        # take max score for each item
        max_scores, _ = torch.max(scores, dim=-1)

        top_scores, top_indices = torch.topk(max_scores, k)

        logger.debug(f"top scores: {top_scores}\ntop indices: {top_indices}")
        items = items_df.iloc[top_indices.tolist()]

        return items["item_id"]

    def search_by_text(self, text, k) -> pd.DataFrame:
        all_items_df = self._get_item_ids()

        logger.debug(f"all items df columns: {all_items_df.columns.tolist()}")

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

        # Extract the embedding arrays from the DataFrame columns
        about_product_embeddings = about_product_embeddings_df["about_product_embedding"].values
        product_name_embeddings = product_name_embeddings_df["product_name_embedding"].values
        category_embeddings = category_embeddings_df["category_embedding"].values

        # Get the tensors
        about_product_tensor = torch.tensor(
            np.stack(about_product_embeddings), dtype=torch.float32
        )
        product_name_tensor = torch.tensor(np.stack(product_name_embeddings), dtype=torch.float32)
        category_tensor = torch.tensor(np.stack(category_embeddings), dtype=torch.float32)
        logger.debug(f"shape of about_product_tensor: {about_product_tensor.shape}")
        logger.debug(f"shape of product_name_tensor: {product_name_tensor.shape}")
        logger.debug(f"shape of category_tensor: {category_tensor.shape}")

        items_embeddings = torch.stack(
            [about_product_tensor, product_name_tensor, category_tensor], dim=1
        )
        logger.info(f"textual features has embeddings tensor of shape: {items_embeddings.shape}")

        free_text_embeddings = self._get_free_text_embeddings(text)
        logger.info(f"embedded free text with shape of: {free_text_embeddings.shape}")

        similarity_scores = self._calculate_similarity_scores(
            free_text_embeddings, items_embeddings
        )

        top_items = self._get_top_k_items(all_items_df, similarity_scores, k=5)
        logger.info(f"top items are:\n{top_items}")
        ids = pd.DataFrame()

        ids["item_id"] = top_items
        ids["event_timestamp"] = pd.to_datetime("now", utc=True)

        item_service = self.store.get_feature_service("item_service")
        values = self.store.get_historical_features(
            entity_df=ids,
            features=item_service,
        ).to_df()

        return values
