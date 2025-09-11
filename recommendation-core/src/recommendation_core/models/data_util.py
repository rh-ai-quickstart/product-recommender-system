import logging
from datetime import datetime

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


# Custom Dataset class
class UserItemMagnitudeDataset(Dataset):
    def __init__(self, items, users, magnitude):
        """
        Args:
            items (dict): Dictionary with keys mapping to tensors of shape (n_samples, n_cols, dim)
            users (dict): Dictionary with keys mapping to tensors of shape (n_samples, n_cols, dim)
            magnitude (tensor): Tensor of shape (n_samples,)
        """
        self.items = items
        self.users = users
        self.magnitude = magnitude

        # Verify that all tensors have consistent number of samples
        n_samples = len(magnitude)
        for user_tensor in users.values():
            assert len(user_tensor) == n_samples, "User tensor size mismatch"
        for item_tensor in items.values():
            assert len(item_tensor) == n_samples, "Item tensor size mismatch"

        self._items_num_numerical = items["numerical_features"].shape[1]
        self._users_num_numerical = users["numerical_features"].shape[1]
        self._items_num_categorical = torch.unique(
            items["categorical_features"]
        ).numel()
        self._users_num_categorical = torch.unique(
            users["categorical_features"]
        ).numel()

    def __len__(self):
        """Returns the total number of samples"""
        return len(self.magnitude)

    def __getitem__(self, idx):
        """Returns a single sample"""

        # Get item data for this index
        item_sample = {key: tensor[idx] for key, tensor in self.items.items()}

        # Get user data for this index
        user_sample = {key: tensor[idx] for key, tensor in self.users.items()}

        # Get magnitude for this index
        magnitude_sample = self.magnitude[idx]

        return item_sample, user_sample, magnitude_sample

    @property
    def items_num_numerical(self):
        """Returns the number of numerical features for items."""
        return self._items_num_numerical

    @property
    def users_num_numerical(self):
        """Returns the number of numerical features for users."""
        return self._users_num_numerical

    @property
    def items_num_categorical(self):
        """Returns the number of categorical features for items."""
        return self._items_num_categorical

    @property
    def users_num_categorical(self):
        """Returns the number of categorical features for users."""
        return self._users_num_categorical


# Assuming df is your DataFrame with textual columns
def tokenize_and_embed_dataframe(df, batch_size=16):
    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
    model = AutoModel.from_pretrained("BAAI/bge-small-en-v1.5")
    model.eval()

    # Get device (GPU if available, else CPU)
    # device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    device = torch.device("cpu")
    logger.info(f"device: {device}")
    model.to(device)

    # Initialize dictionary to store embeddings for each column
    embeddings_columns = []

    # Process each column
    for column in df.columns:
        logger.info(f"Processing column: {column}")
        texts = df[column].astype(str).tolist()

        # Initialize array to store embeddings
        embeddings = []

        # Process in batches
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
            batch_texts = texts[i : i + batch_size]

            # Tokenize
            encoded_input = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                return_tensors="pt",
                # max_length=512  # Adjust based on model requirements
            )

            # Move to device
            encoded_input = {k: v.to(device) for k, v in encoded_input.items()}

            # Compute embeddings
            with torch.inference_mode():
                model_output = model(**encoded_input)
                # CLS pooling
                batch_embeddings = model_output[0][:, 0]
                # Normalize
                batch_embeddings = torch.nn.functional.normalize(
                    batch_embeddings, p=2, dim=1
                )

            # Move to CPU and convert to numpy
            embeddings.append(batch_embeddings.cpu())
            # break

        # Concatenate all batch embeddings
        column_embeddings = torch.vstack(embeddings)  # shape: len(df), dim

        # Store in dictionary
        embeddings_columns.append(column_embeddings)

    return torch.stack(embeddings_columns).permute(
        1, 0, 2
    )  # shape: (len(df), n_col, dim)


def data_preproccess(df: pd.DataFrame):
    # filter unwanted features
    df = df[
        [
            col
            for col in df.columns
            if not col.endswith("timestamp") and not col.endswith("_id")
        ]
    ]

    # Numerical features
    numerical_df = df.select_dtypes(include="number")
    datetime_df = df.select_dtypes(include="datetime")
    for datetime_col in datetime_df.columns:
        datetime_df[datetime_col] = datetime_df[datetime_col].apply(
            lambda x: x.toordinal()
        )
    numerical_df = pd.concat([numerical_df, datetime_df], axis=1)

    text_columns = list(set(df.columns) - set(numerical_df.columns))

    # Image features
    url_columns = [
        col
        for col in text_columns
        if (df[col].astype(str).str.lower().str[:4] == "http").mean() > 0.5
    ]
    url_image_df = df[url_columns].astype(str)

    # Calculate the percentage of unique values for each column
    unique_percentages = df[
        [col for col in text_columns if col not in url_columns]
    ].nunique()
    unique_percentages = unique_percentages / unique_percentages.max()
    # Filter columns where unique values are less than 20% of total values
    categorical_columns = unique_percentages[unique_percentages < 0.8].index.tolist()
    category_df = df[categorical_columns]
    logger.info(f"unqiue precentege: {unique_percentages}")
    # Text features
    text_columns = [
        col for col in text_columns if col not in categorical_columns + url_columns
    ]
    text_df = df[text_columns]

    def df_to_tensor(df: pd.DataFrame):
        tensor = torch.Tensor(df.values)
        # if tensor.dim() == 2:
        #     tensor = tensor.unsqueeze(-1)
        if tensor.dim() == 1:
            tensor = tensor.view(-1, 1)
        if tensor.dim() == 0:
            raise ValueError("one of the tensors is empty")
        return tensor

    def parse_categorical_df(df: pd.DataFrame):
        df = df.copy()
        for col in df.columns:
            df[col] = col + "_" + df[col].astype(str)

        unique_values = np.unique(df.values.flatten())
        category_to_code = {val: idx for idx, val in enumerate(unique_values)}

        # Apply label encoding to the entire DataFrame
        numeric_df = df.apply(lambda x: x.map(category_to_code))
        return numeric_df

    procceed_tensor_dict = {
        "numerical_features": df_to_tensor(numerical_df),  # shape: (len(df), n_col)
        "categorical_features": df_to_tensor(parse_categorical_df(category_df)).to(
            int
        ),  # shape: (len(df), n_col)
        "text_features": tokenize_and_embed_dataframe(
            text_df
        ),  # shape: (len(df), n_col, dim)
        "url_image": url_image_df.values.tolist(),  # shape: (len(df), n_col)
    }

    # The returned dictionary is used to create a UserItemMagnitudeDataset.
    # The proccceeded tensor dict will conceptually look like this:
    # item_dict = {
    # "numerical_features": torch.Tensor([
    #     [120.50, 4.5],  # Item 1: price, rating
    #     [15.00, 4.8],   # Item 2: price, rating
    #     [299.99, 4.9]   # Item 3: price, rating
    # ]),
    # "categorical_features": torch.Tensor([
    #     [5],  # Item 1: brand_id
    #     [12], # Item 2: brand_id
    #     [8]   # Item 3: brand_id
    # ]).to(int),
    # "text_features": torch.Tensor([
    #     [[0.1, 0.8, ...]],  # Item 1: name_embedding
    #     [[0.4, 0.2, ...]],  # Item 2: name_embedding
    #     [[0.9, 0.5, ...]]   # Item 3: name_embedding
    # ]),
    # "url_image": [
    #     ["/.../kettle.png"],
    #     ["/.../usbc.png"],
    #     ["/.../stove.png"]
    # ]
    #}   
    return procceed_tensor_dict


def preprocess_pipeline(
    items_df: pd.DataFrame, users_df: pd.DataFrame, interactions_df: pd.DataFrame
):
    # Align the interactions with the users and items
    items_df, users_df, inter_df = _align_and_clean_interactions(items_df, users_df, interactions_df)
    magnitude = torch.Tensor(_calculate_interaction_loss(inter_df).values)

    item_dict = data_preproccess(items_df)
    user_dict = data_preproccess(users_df)

    return UserItemMagnitudeDataset(item_dict, user_dict, magnitude)


def _align_and_clean_interactions(
    items_df: pd.DataFrame, users_df: pd.DataFrame, interactions_df: pd.DataFrame
):
    # Join interactions to items (on item_id) and then to users (on user_id)
    # to ensure each training row has aligned item and user features for that
    # interaction. Inner joins drop orphaned interactions with missing keys.
    # So, this merge is being done to have clean data for downstream preprocessing.
    merged_df = interactions_df.merge(items_df, on="item_id").merge(users_df, on="user_id")
    # During merging, if constituents being merged contain similar column names,
    # pandas suffixes duplicate columns (e.g., rating_x from
    # interactions and rating_y from items). We rename back to the expected
    # schema (no suffix) and slice the merged frame to exactly match the
    # original columns for each view, so downstream preprocessing remains
    # consistent with the source schemas.
    return (
        merged_df.rename(columns={"rating_y": "rating"})[items_df.columns],
        merged_df[users_df.columns],
        merged_df.rename(columns={"rating_x": "rating"})[interactions_df.columns],
    )


def _loss_map(factor, none_value):
    return {
        "interaction_type": {
            "positive_view": lambda x: x / factor,
            "negative_view": lambda x: x * factor,
            "cart": lambda x: x / (factor * 3),
            "purchase": lambda x: x / (factor * 10),
            "rate": lambda x: x,
            none_value: lambda x: x,
        },
        "rating": lambda x, r: (
            x
            if (r is none_value or r == 3.0)
            else x * (factor * (3 - r)) if r <= 2.0 else x / (factor * (r - 2))
        ),
        "quantity": lambda x, q: (
            x if (q is none_value or q <= 1.0) else x / (factor * (q - 1))
        ),
    }


def _calculate_interaction_loss(
    inter_df: pd.DataFrame,
    factor: float = 1.1,
    magnitude_default: float = 11.265591558187197,
):
    none_value = object()
    punishment = _loss_map(factor, none_value)
    inter_df = inter_df.fillna(none_value)
    inter_df["magnitude"] = magnitude_default

    # Apply interaction type transformation
    inter_df["magnitude"] = inter_df.apply(
        lambda row: punishment["interaction_type"].get(
            row["interaction_type"], lambda x: x
        )(row["magnitude"]),
        axis=1,
    )

    # Apply rating transformation
    inter_df["magnitude"] = inter_df.apply(
        lambda row: punishment["rating"](row["magnitude"], row["rating"]), axis=1
    )

    # Apply quantity transformation
    inter_df["magnitude"] = inter_df.apply(
        lambda row: punishment["quantity"](row["magnitude"], row["quantity"]), axis=1
    )

    return inter_df["magnitude"]


def clean_dataset(df: pd.DataFrame):
    # Parse number features
    df["discounted_price"] = df["discounted_price"].str.replace("₹", "")
    df["discounted_price"] = df["discounted_price"].str.replace(",", "")
    df["discounted_price"] = df["discounted_price"].astype("float64")

    df["actual_price"] = df["actual_price"].str.replace("₹", "")
    df["actual_price"] = df["actual_price"].str.replace(",", "")
    df["actual_price"] = df["actual_price"].astype("float64")

    df["discount_percentage"] = (
        df["discount_percentage"].str.replace("%", "").astype("float64")
    )
    df["discount_percentage"] = df["discount_percentage"] / 100

    df["rating"] = df["rating"].str.replace("|", "3.9").astype("float64")
    df["rating_count"] = df["rating_count"].str.replace(",", "").astype("float64")

    # Fill null values
    df["rating_count"] = df.rating_count.fillna(value=df["rating_count"].median())

    # Drop duplicated rows
    df.drop_duplicates(inplace=True)

    # Parse columns which have many values
    df["user_id"] = df["user_id"].str.split(",")
    df["user_name"] = df["user_name"].str.split(",")
    df["review_title"] = df["review_title"].str.split(",")
    df["review_content"] = df["review_content"].str.split(",")
    df["review_id"] = df["review_id"].str.split(",")

    # make sure the length is the same
    emtpy_lst = [""] * 8
    df["review_title"] = df.apply(
        lambda row: (row["review_title"] + emtpy_lst)[: len(row["user_id"])], axis=1
    )
    df["review_content"] = df.apply(
        lambda row: (row["review_content"] + emtpy_lst)[: len(row["user_id"])], axis=1
    )
    df["review_id"] = df.apply(
        lambda row: (row["review_id"] + emtpy_lst)[: len(row["user_id"])], axis=1
    )

    # Ensure the lengths match for each row
    df = df[df["user_id"].str.len() == df["user_name"].str.len()]

    item_columns = [
        "product_id",
        "product_name",
        "category",
        "discounted_price",
        "actual_price",
        "discount_percentage",
        "rating",
        "rating_count",
        "about_product",
        "img_link",
        "product_link",
    ]
    user_columns = ["user_id", "user_name", "category"]
    interactions_columns = [
        "review_id",
        "user_id",
        "product_id",
        "rating",
        "review_title",
        "review_content",
    ]

    # align dataset to last dataset
    item_df = df[item_columns].rename(columns={"product_id": "item_id"})
    item_df["arrival_date"] = datetime(2023, 1, 1)

    df = df.explode(
        ["user_id", "user_name", "review_title", "review_content", "review_id"]
    )

    user_df = df[user_columns]
    user_df = user_df.rename(columns={"category": "preferences"})
    user_df = (
        user_df.groupby(["user_id", "user_name"])["preferences"]
        .apply(lambda x: "|".join(set(x)))
        .reset_index()
    )
    user_df["signup_date"] = datetime(2023, 1, 1)

    interaction_df = df[interactions_columns].rename(
        columns={"product_id": "item_id", "review_id": "interaction_id"}
    )

    interaction_df["interaction_type"] = "review"
    interaction_df["timestamp"] = datetime(2025, 1, 1)
    interaction_df["quantity"] = None

    return item_df, user_df, interaction_df
