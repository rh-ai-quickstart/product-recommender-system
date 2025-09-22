from feast import FeatureService
from feature_views import (
    interaction_feature_view,
    item_clip_features_embed_view,
    item_embedding_view,
    item_feature_view,
    item_textual_features_embed_view,
    item_name_features_embed_view,
    item_category_features_embed_view,
    user_feature_view,
    user_items_view,
)

item_feature_service = FeatureService(name="item_service", features=[item_feature_view])
user_feature_service = FeatureService(name="user_service", features=[user_feature_view])
interactions_feature_service = FeatureService(
    name="interaction_service", features=[interaction_feature_view]
)
item_embedding_service = FeatureService(name="item_embedding", features=[item_embedding_view])
user_top_k_items_service = FeatureService(name="user_top_k_items", features=[user_items_view])
item_textual_features_embed_view_service = FeatureService(
    name="item_textual_features_embed", features=[item_textual_features_embed_view]
)
item_name_features_embed_view_service = FeatureService(
    name="item_name_features_embed", features=[item_name_features_embed_view]
)
item_category_features_embed_view_service = FeatureService(
    name="item_category_features_embed", features=[item_category_features_embed_view]
)
item_clip_features_embed_view_service = FeatureService(
    name="item_clip_features_embed", features=[item_clip_features_embed_view]
)
