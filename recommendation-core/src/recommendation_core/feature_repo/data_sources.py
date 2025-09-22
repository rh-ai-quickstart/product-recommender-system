import os

from feast import FileSource, PushSource
from feast.data_format import ParquetFormat

data_path = "data"

users_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "recommendation_users.parquet"),
    timestamp_field="signup_date",
)
interactions_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "recommendation_interactions.parquet"),
    timestamp_field="timestamp",
)
items_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "recommendation_items.parquet"),
    timestamp_field="arrival_date",
)
items_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "dummy_item_embed.parquet"),
    timestamp_field="event_timestamp",
)
users_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "dummy_user_embed.parquet"),
    timestamp_field="event_timestamp",
)
users_items_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "user_items.parquet"),
    timestamp_field="event_timestamp",
)
item_textual_features_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "item_textual_features_embed.parquet"),
    timestamp_field="event_timestamp",
)
item_clip_features_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "item_clip_features_embed.parquet"),
    timestamp_field="event_timestamp",
)
item_name_features_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "item_name_features_embed.parquet"),
    timestamp_field="event_timestamp",
)

item_category_features_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "item_category_features_embed.parquet"),
    timestamp_field="event_timestamp",
)

item_embed_push_source = PushSource(
    name="item_embed_push_source", batch_source=items_embed_dummy_source
)

user_embed_push_source = PushSource(
    name="user_embed_push_source", batch_source=users_embed_dummy_source
)

user_items_push_source = PushSource(
    name="user_items_push_source", batch_source=users_items_dummy_source
)

item_textual_features_embed_push_source = PushSource(
    name="item_textual_features_embed",
    batch_source=item_textual_features_embed_dummy_source,
)

item_name_features_embed_push_source = PushSource(
    name="item_name_features_embed",
    batch_source=item_name_features_embed_dummy_source,
)

item_category_features_embed_push_source = PushSource(
    name="item_category_features_embed",
    batch_source=item_category_features_embed_dummy_source,
)

item_clip_features_embed_push_source = PushSource(
    name="item_clip_features_embed", batch_source=item_clip_features_embed_dummy_source
)
