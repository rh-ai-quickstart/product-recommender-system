import pandas as pd
import torch
from feast import FeatureStore
from transformers import AutoModel, AutoTokenizer

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class SearchService:

    def __init__(self, store: FeatureStore):
        self.store = store
        self.tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(EMBEDDING_MODEL)
        self.model.eval()

    def search_by_text(self, text, k):
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
            batch_embeddings = torch.nn.functional.normalize(
                batch_embeddings, p=2, dim=1
            )

        user_embed = batch_embeddings.cpu().detach().numpy()

        ids = self.store.retrieve_online_documents(
            query=list(user_embed[0]),
            top_k=k,
            features=["item_textual_features_embed:item_id"],
        ).to_df()
        ids["event_timestamp"] = pd.to_datetime("now", utc=True)

        item_service = self.store.get_feature_service("item_service")
        values = self.store.get_historical_features(
            entity_df=ids,
            features=item_service,
        ).to_df()
        return values
