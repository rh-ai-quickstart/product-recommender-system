# Adding a New Feature Store to Feast

This guide documents the process of adding a new feature store/table to the Feast feature store system, based on the implementation of the `item_name_features_embed` store for product name embeddings.

## Overview

Adding a new feature store involves:
1. Creating dummy data files
2. Defining data sources (batch and push sources)
3. Creating feature views
4. Adding feature services
5. Updating training workflows
6. Deploying changes

## Step-by-Step Process

### 1. Create Dummy Data File

**Location:** `recommendation-core/src/recommendation_core/feature_repo/data/`

Create a dummy parquet file with the expected schema:

```python
import pandas as pd
import numpy as np
from datetime import datetime

# Create dummy data matching the expected schema
dummy_data = {
    'item_id': ['dummy_item_1'],
    'your_embedding_field': [np.array([0.1, 0.2])],  # Adjust dimensions as needed
    'event_timestamp': [datetime.now()]
}

df = pd.DataFrame(dummy_data)
df.to_parquet('data/your_new_store.parquet', index=False)
```

**Requirements:**
- Must include entity ID field (e.g., `item_id`, `user_id`)
- Must include `event_timestamp` field
- Array fields should be numpy arrays (for embeddings)
- Save as `.parquet` format

### 2. Define Data Sources

**File:** `recommendation-core/src/recommendation_core/feature_repo/data_sources.py`

Add batch source and push source definitions:

```python
# Add batch/dummy source
your_store_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "your_new_store.parquet"),
    timestamp_field="event_timestamp",
)

# Add push source
your_store_push_source = PushSource(
    name="your_store_name",  # This name must match what you use in store.push()
    batch_source=your_store_dummy_source,
)
```

**Important Notes:**
- The `name` parameter in PushSource must match the string used in `store.push()`
- Use consistent naming convention
- Ensure dummy source file exists

### 3. Create Feature View

**File:** `recommendation-core/src/recommendation_core/feature_repo/feature_views.py`

Add the import and feature view definition:

```python
# Add to imports
from data_sources import (
    # ... existing imports
    your_store_push_source,
)

# Define feature view
your_store_view = FeatureView(
    name="your_store_name",  # Must match push source name
    entities=[appropriate_entity],  # e.g., item_entity, user_entity
    ttl=timedelta(days=365 * 5),
    schema=[
        Field(name="item_id", dtype=String),  # Entity ID
        Field(
            name="your_embedding_field",
            dtype=Array(Float32),
            vector_index=True,  # Enable for vector search
            vector_search_metric="cosine",  # or "euclidean"
        ),
    ],
    source=your_store_push_source,
    online=True,  # Enable for online serving
)
```

**Key Points:**
- Feature view `name` must match push source `name`
- Use `Array(Float32)` for embedding fields
- Set `vector_index=True` for searchable embeddings
- Include all fields that will be pushed to the store

### 4. Add Feature Service

**File:** `recommendation-core/src/recommendation_core/feature_repo/feature_services.py`

Add import and service definition:

```python
# Add to imports
from feature_views import (
    # ... existing imports
    your_store_view,
)

# Add feature service
your_store_service = FeatureService(
    name="your_store_service",
    features=[your_store_view]
)
```

### 5. Update Training Workflow

**File:** `recommendation-training/train-workflow.py`

Add code to extract embeddings and push to the new store:

```python
# Extract your embeddings (example for product name embeddings)
your_embeddings_df = item_df[["item_id"]].copy()
your_embeddings_df["your_embedding_field"] = (
    extracted_embeddings.detach().numpy().tolist()  # Convert to list
)
your_embeddings_df["event_timestamp"] = current_time

# Push to the store
store.push(
    "your_store_name",  # Must match push source name
    your_embeddings_df,
    to=PushMode.ONLINE,
    allow_registry_cache=False,
)
```

Add to materialization list:

```python
store.materialize_incremental(
    current_time,
    feature_views=[
        # ... existing views
        "your_store_name",  # Add your new store
    ],
)
```

### 6. Deploy Changes

1. **Commit and push changes to Git:**
   ```bash
   git add recommendation-core/src/recommendation_core/feature_repo/
   git commit -m "Add new feature store: your_store_name"
   git push origin your-branch
   ```

2. **Redeploy the application** to pick up changes from Git

3. **Verify feast-apply-job runs successfully:**
   ```bash
   kubectl get jobs -l feast.dev/name=feast-recommendation
   kubectl logs job/feast-apply-job
   ```

## Common Issues and Solutions

### Issue: Push Source Not Found
**Error:** `PushSourceNotFoundException: Unable to find push source 'your_store_name'`

**Solutions:**
- Verify push source name matches in `data_sources.py` and `store.push()`
- Ensure feast-apply-job ran after your Git changes
- Check Git branch configuration in Helm template

### Issue: Vector Validation Error
**Error:** `KeyError: 'your_field_name'`

**Solutions:**
- Ensure DataFrame columns match feature view schema exactly
- Check that vector fields are properly configured with `Array(Float32)`
- Verify dummy data file has the correct schema

### Issue: Schema Mismatch
**Error:** Column not found during materialization

**Solutions:**
- Ensure all fields in feature view schema are present in pushed DataFrame
- Check data types match (Array fields should be lists of floats)
- Verify entity fields are included

### Issue: Registry Cache
**Error:** Old feature definitions being used

**Solutions:**
- Add `store.refresh_registry()` before operations
- Restart feast-apply-job to pull latest Git changes
- Check Git configuration in feature store deployment

## Best Practices

1. **Naming Conventions:**
   - Use consistent naming across all components
   - Push source name = Feature view name = Store push name

2. **Data Types:**
   - Use `Array(Float32)` for embeddings
   - Use `String` for IDs
   - Always include `event_timestamp`

3. **Vector Search:**
   - Set `vector_index=True` for searchable embeddings
   - Choose appropriate `vector_search_metric` (cosine/euclidean)

4. **Testing:**
   - Create meaningful dummy data for testing
   - Test push operations with try/catch blocks
   - Verify materialization includes new store

5. **Documentation:**
   - Document the purpose of each new store
   - Include field descriptions
   - Note any special requirements or dependencies

## Example: Product Name Embeddings Store

Here's the complete implementation for the product name embeddings store:

### Dummy Data
```python
dummy_data = {
    'item_id': ['dummy_item_1'],
    'product_name_embedding': [np.array([0.1, 0.2])],
    'event_timestamp': [datetime.now()]
}
```

### Data Sources
```python
item_name_features_embed_dummy_source = FileSource(
    file_format=ParquetFormat(),
    path=os.path.join(data_path, "item_name_features_embed.parquet"),
    timestamp_field="event_timestamp",
)

item_name_features_embed_push_source = PushSource(
    name="item_name_features_embed",
    batch_source=item_name_features_embed_dummy_source,
)
```

### Feature View
```python
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
```

### Training Code
```python
# Extract product name embeddings
item_name_features = item_df[["item_id"]].copy()
item_name_features["product_name_embedding"] = (
    processed_items["text_features"].detach()[:, 0, :].numpy().tolist()
)
item_name_features["event_timestamp"] = current_time

# Push to store
store.push(
    "item_name_features_embed",
    item_name_features,
    to=PushMode.ONLINE,
    allow_registry_cache=False,
)
```

This implementation allows for separate storage and retrieval of product name embeddings for enhanced search capabilities.
