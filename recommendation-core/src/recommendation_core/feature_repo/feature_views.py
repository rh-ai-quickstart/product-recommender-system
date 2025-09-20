from datetime import timedelta

from data_sources import (interactions_source,
                          item_clip_features_embed_push_source,
                          item_embed_push_source,
                          item_textual_features_embed_push_source,
                          item_name_features_embed_push_source,
                          item_category_features_embed_push_source,
                          items_source, user_embed_push_source,
                          user_items_push_source, users_source)
from entities import item_entity, user_entity
from feast import FeatureView, Field
from feast.types import Array, Float32, Float64, Int64, String

user_feature_view = FeatureView(
    name="user_features",
    entities=[user_entity],
    ttl=timedelta(days=365 * 6),
    schema=[
        Field(name="user_id", dtype=String),
        Field(name="user_name", dtype=String),
        Field(name="preferences", dtype=String),
    ],
    source=users_source,
    online=False,
)

item_feature_view = FeatureView(
    name="item_features",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(name="product_name", dtype=String),
        Field(name="category", dtype=String),
        Field(name="discounted_price", dtype=Float64),
        Field(name="actual_price", dtype=Float64),
        Field(name="discount_percentage", dtype=Float64),
        Field(name="rating", dtype=Float64),
        Field(name="rating_count", dtype=Int64),
        Field(name="about_product", dtype=String),
        Field(name="img_link", dtype=String),
        Field(name="product_link", dtype=String),
    ],
    source=items_source,
    online=True,
)

interaction_feature_view = FeatureView(
    name="interactions_features",
    entities=[user_entity, item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="interaction_id", dtype=String),
        Field(name="user_id", dtype=String),
        Field(name="item_id", dtype=String),
        Field(name="rating", dtype=Float64),
        Field(name="review_title", dtype=String),
        Field(name="review_content", dtype=String),
        Field(name="interaction_type", dtype=String),
        Field(name="quantity", dtype=Float64),
    ],
    source=interactions_source,
    online=False,
)
# interaction_stream_feature_view = FeatureView(
#     name="interactions_stream_features",
#     entities=[user_entity, item_entity],
#     ttl=timedelta(days=365 * 5),
#     schema=[
#         Field(name="user_id", dtype=Int64),
#         Field(name="item_id", dtype=Int64),
#         Field(name="interaction_type", dtype=String),
#         Field(name="rating", dtype=Int32),
#         Field(name="quantity", dtype=Int32),
#     ],
#     source=interaction_stream_source,
#     online=False
# )

# @stream_feature_view(
#     entities=[user_entity, item_entity],
#     ttl=timedelta(days=365 * 5),
#     mode="spark",
#     schema=[
#         Field(name="user_id", dtype=Int64),
#         Field(name="item_id", dtype=Int64),
#         Field(name="interaction_type", dtype=String),
#         Field(name="rating", dtype=Int32),
#         Field(name="quantity", dtype=Int32),
#     ],
#     timestamp_field="event_timestamp",
#     online=True,
#     source=interaction_stream_source,
#     tags={},
# )
# def iteractions_stream(df):
#     return df

# interaction_stream_feature_view = StreamFeatureView(
#     name='interaction_stream_features',
#     source=interaction_stream_source,
#     entities=[user_entity, item_entity],
#     ttl=timedelta(days=365 * 5),
#     # mode="spark",
#     schema=[
#         Field(name="user_id", dtype=Int64),
#         Field(name="item_id", dtype=Int64),
#         Field(name="interaction_type", dtype=String),
#         Field(name="rating", dtype=Int32),
#         Field(name="quantity", dtype=Int32),
#     ],
#     timestamp_field="event_timestamp",
#     online=True,
#     # tags={},
# )

item_embedding_view = FeatureView(
    name="item_embedding",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(
            name="embedding",
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=item_embed_push_source,
    online=True,
)

user_embedding_view = FeatureView(
    name="user_embedding",
    entities=[user_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="user_id", dtype=String),
        Field(
            name="embedding",
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=user_embed_push_source,
    online=True,
)

user_items_view = FeatureView(
    name="user_items",
    entities=[user_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="user_id", dtype=String),
        Field(name="top_k_item_ids", dtype=Array(String), vector_index=False),
    ],
    source=user_items_push_source,
    online=True,
)

item_textual_features_embed_view = FeatureView(
    name="item_textual_features_embed",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(
            name="about_product_embedding",
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=item_textual_features_embed_push_source,
    online=True,
)

item_name_features_embed_view = FeatureView(
    name="item_name_features_embed",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(
            name="product_name_embedding",
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=item_name_features_embed_push_source,
    online=True,
)

item_category_features_embed_view = FeatureView(
    name="item_category_features_embed",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(
            name="category_embedding",
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=item_category_features_embed_push_source,
    online=True,
)


item_clip_features_embed_view = FeatureView(
    name="item_clip_features_embed",
    entities=[item_entity],
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),
        Field(
            name="clip_latent_space_embedding",  # a unique space for text and images
            dtype=Array(Float32),
            vector_index=True,
            vector_search_metric="cosine",
        ),
    ],
    source=item_clip_features_embed_push_source,
    online=True,
)
