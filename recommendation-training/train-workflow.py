import os
from typing import NamedTuple

from kfp import Client, compiler, dsl, kubernetes
from kfp.dsl import Artifact, Dataset, Input, Model, Output
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

BASE_IMAGE = os.getenv(
    "BASE_REC_SYS_IMAGE", "quay.io/rh-ai-quickstart/recommendation-core:latest"
)


@dsl.component(base_image=BASE_IMAGE)
def generate_candidates(
    item_input_model: Input[Model],
    user_input_model: Input[Model],
    item_df_input: Input[Dataset],
    user_df_input: Input[Dataset],
    models_definition_input: Input[Artifact],
):
    import json
    import logging
    import subprocess
    from datetime import datetime

    import pandas as pd
    import torch
    from feast import FeatureStore
    from feast.data_source import PushMode
    from recommendation_core.models.data_util import data_preproccess
    from recommendation_core.models.entity_tower import EntityTower
    from recommendation_core.service.clip_encoder import ClipEncoder
    from torch.utils.data import DataLoader, TensorDataset

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    with open(models_definition_input.path, "r") as f:
        models_definition: dict = json.load(f)

    with open("src/recommendation_core/feature_repo/feature_store.yaml", "r") as file:
        logger.info(file.read())

    store = FeatureStore(repo_path="src/recommendation_core/feature_repo/")

    # device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    device = torch.device("cpu")
    logger.debug("models_definition items")
    logger.debug(f"models_definition['items_num_numerical']: {models_definition['items_num_numerical']}")
    logger.debug(f"models_definition['items_num_categorical']: {models_definition['items_num_categorical']}")
    item_encoder = EntityTower(
        models_definition["items_num_numerical"],
        models_definition["items_num_categorical"],
    )
    logger.debug("models_definition users")
    logger.debug(f"models_definition['users_num_numerical']: {models_definition['users_num_numerical']}")
    logger.debug(f"models_definition['users_num_categorical']: {models_definition['users_num_categorical']}")
    user_encoder = EntityTower(
        models_definition["users_num_numerical"],
        models_definition["users_num_categorical"],
    )
    item_encoder.load_state_dict(torch.load(item_input_model.path))
    user_encoder.load_state_dict(torch.load(user_input_model.path))
    item_encoder.to(device)
    user_encoder.to(device)
    item_encoder.eval()
    user_encoder.eval()
    # load item and user dataframes
    item_df = pd.read_parquet(item_df_input.path)
    user_df = pd.read_parquet(user_df_input.path)

    # Create a new table to be push to the online store
    item_embed_df = item_df[["item_id"]].copy()
    user_embed_df = user_df[["user_id"]].copy()

    # Encode the items and users
    proccessed_items = data_preproccess(item_df)
    proccessed_users = data_preproccess(user_df)

    logger.debug("proccessed_items")
    for key, value in proccessed_items.items():
        logger.debug(f"proccessed_items[{key}]: {type(value)}")
        if hasattr(value, 'shape'):
            logger.debug(f"proccessed_items[{key}]: {value.shape}")
        else:
            logger.debug(f"proccessed_items[{key}]: {len(value)}")
            logger.debug(f"proccessed_items[{key}]: {value}")

    logger.debug("****************************************")
    logger.debug("proccessed_users")
    for key, value in proccessed_users.items():
        logger.debug(f"proccessed_users[{key}]: {type(value)}")
        if hasattr(value, 'shape'):
            logger.debug(f"proccessed_users[{key}]: {value.shape}")
        else:
            logger.debug(f"proccessed_users[{key}]: {len(value)}")
            logger.debug(f"proccessed_users[{key}]: {value}")

    # Move tensors to device
    proccessed_items = {
        key: value.to(device) if isinstance(value, torch.Tensor) else value
        for key, value in proccessed_items.items()
    }
    proccessed_users = {
        key: value.to(device) if isinstance(value, torch.Tensor) else value
        for key, value in proccessed_users.items()
    }
    # Ensure categorical indices are within embedding vocab
    def _sanitize_categorical(x, num_embeddings: int, name: str):
        if not isinstance(x, torch.Tensor):
            raise ValueError(f"{name} categorical_features must be a Tensor")
        x = x.long()
        if num_embeddings > 0:
            x = torch.clamp(x, 0, num_embeddings - 1)
        try:
            logger.debug(
                f"{name} categorical idx range after clamp: "
                f"[{int(x.min().item())}, {int(x.max().item())}] "
                f"vs allowed [0, {num_embeddings-1}]"
            )
        except Exception:
            pass
        return x

    #if hasattr(item_encoder, "categorical_embed") and "categorical_features" in proccessed_items:
    #    proccessed_items["categorical_features"] = _sanitize_categorical(
    #        proccessed_items["categorical_features"],
    #        item_encoder.categorical_embed.num_embeddings,
    #        "items",
    #    )

    #if hasattr(user_encoder, "categorical_embed") and "categorical_features" in proccessed_users:
    #    proccessed_users["categorical_features"] = _sanitize_categorical(
    #        proccessed_users["categorical_features"],
    #        user_encoder.categorical_embed.num_embeddings,
    #        "users",
    #    )

    item_embed_df["embedding"] = item_encoder(**proccessed_items).detach().numpy().tolist()

    # Process users in batches
    BATCH_SIZE = 256  # Adjust based on available memory
    user_embeddings = []

    # Create tensors for each feature
    numerical_features = proccessed_users["numerical_features"]
    #categorical_features = proccessed_users["categorical_features"]
    text_features = proccessed_users["text_features"]
    url_images = proccessed_users["url_image"]

    # Create dataset and dataloader
    #dataset = TensorDataset(numerical_features, categorical_features, text_features)
    dataset = TensorDataset(numerical_features, text_features)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE)

    # Process in batches
    user_encoder.eval()
    with torch.inference_mode():
        #for batch_num, (batch_numerical, batch_categorical, batch_text) in enumerate(dataloader):
        for batch_num, (batch_numerical, batch_text) in enumerate(dataloader):
            # Move to device
            batch_numerical = batch_numerical.to(device)
            #batch_categorical = batch_categorical.to(device)
            batch_text = batch_text.to(device)

            # Get batch of url_images
            start_idx = batch_num * BATCH_SIZE
            end_idx = start_idx + len(batch_numerical)
            batch_url_images = url_images[start_idx:end_idx]

            # Create batch dict
            batch_dict = {
                "numerical_features": batch_numerical,
                #"categorical_features": batch_categorical,
                "text_features": batch_text,
                "url_image": batch_url_images
            }

            # Get embeddings for batch
            batch_embeddings = user_encoder(**batch_dict).detach().cpu().numpy()
            user_embeddings.extend(batch_embeddings.tolist())

    # Assign embeddings to dataframe
    user_embed_df["embedding"] = user_embeddings

    # Add the currnet timestamp
    current_time = datetime.now()
    item_embed_df["event_timestamp"] = current_time
    user_embed_df["event_timestamp"] = current_time

    # Push the new embedding to the offline and online store
    store.push(
        "item_embed_push_source",
        item_embed_df,
        to=PushMode.ONLINE,
        allow_registry_cache=False,
    )
    store.push(
        "user_embed_push_source",
        user_embed_df,
        to=PushMode.ONLINE,
        allow_registry_cache=False,
    )

    # Store the embedding of text features for search by text
    item_text_features_embed = item_df[["item_id"]].copy()
    # item_text_features_embed["product_name"] = (
    #    proccessed_items["text_features"].detach()[:, 0, :].numpy().tolist()
    # )
    item_text_features_embed["product_name"] = (
        proccessed_items["text_features"].detach()[:, 0, :].numpy().tolist()
    )
    item_text_features_embed["about_product_embedding"] = (
        proccessed_items["text_features"].detach()[:, 1, :].numpy().tolist()
    )
    item_text_features_embed["event_timestamp"] = current_time

    store.push(
        "item_textual_features_embed",
        item_text_features_embed,
        to=PushMode.ONLINE,
        allow_registry_cache=False,
    )

    # Store the embedding of clip features for search by image
    clip_encoder = ClipEncoder()
    item_clip_features_embed = clip_encoder.clip_embeddings(item_df)
    store.push(
        "item_clip_features_embed",
        item_clip_features_embed,
        to=PushMode.ONLINE,
        allow_registry_cache=False,
    )

    # Materilize the online store
    store.materialize_incremental(
        current_time,
        feature_views=[
            "item_embedding",
            "user_items",
            "item_features",
            "item_textual_features_embed",
        ],
    )

    # Calculate user recommendations for each user
    item_embedding_view = "item_embedding"
    k = 64
    item_recommendation = []
    for user_embed in user_embed_df["embedding"]:
        item_recommendation.append(
            store.retrieve_online_documents(
                query=user_embed, top_k=k, features=[f"{item_embedding_view}:item_id"]
            )
            .to_df()["item_id"]
            .to_list()
        )

    # Pushing the calculated items to the online store
    user_items_df = user_embed_df[["user_id"]].copy()
    user_items_df["event_timestamp"] = current_time
    user_items_df["top_k_item_ids"] = item_recommendation

    store.push(
        "user_items_push_source",
        user_items_df,
        to=PushMode.ONLINE,
        allow_registry_cache=False,
    )


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["minio", "psycopg2-binary"])
def train_model(
    item_df_input: Input[Dataset],
    user_df_input: Input[Dataset],
    interaction_df_input: Input[Dataset],
    item_output_model: Output[Model],
    user_output_model: Output[Model],
    models_definition_output: Output[Artifact],
) -> NamedTuple(
    "modelMetadata",
    [
        ("bucket_name", str),
        ("new_version", str),
        ("object_name", str),
        ("torch_version", str),
    ],
):
    import json
    import os

    import pandas as pd
    import torch
    from minio import Minio
    from recommendation_core.models.train_two_tower import create_and_train_two_tower
    from sqlalchemy import create_engine, text
    import logging

    logger = logging.getLogger(__name__)

    logger.debug("train_model function started")
    logger.debug(f"item_df_input.path = {item_df_input.path}")
    logger.debug(f"user_df_input.path = {user_df_input.path}")
    logger.debug(f"interaction_df_input.path = {interaction_df_input.path}")

    items_df = pd.read_parquet(item_df_input.path)
    users_df = pd.read_parquet(user_df_input.path)
    interactions_df = pd.read_parquet(interaction_df_input.path)

    item_encoder, user_encoder, models_definition = create_and_train_two_tower(
        items_df=items_df, users_df=users_df, interactions_df=interactions_df, return_model_definition=True
    )

    torch.save(item_encoder.state_dict(), item_output_model.path)
    torch.save(user_encoder.state_dict(), user_output_model.path)
    item_output_model.metadata["framework"] = "pytorch"
    user_output_model.metadata["framework"] = "pytorch"
    with open(models_definition_output.path, "w") as f:
        json.dump(models_definition, f)

    logger.debug("About to create database engine")
    logger.debug(f"DATABASE_URL = {os.getenv('DATABASE_URL', 'NOT_SET')}")
    logger.debug(f"uri = {os.getenv('uri', 'NOT_SET')}")

    #
    engine = create_engine(os.getenv("uri", None))
    logger.debug("DEBUG: Database engine created successfully")

    # Check if table exists
    def table_exists(engine, table_name):
        logger.debug(f"Checking if table '{table_name}' exists")
        query = text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :table_name"
        )
        with engine.connect() as connection:
            result = connection.execute(query, {"table_name": table_name}).scalar()
            logger.debug(f"Table '{table_name}' exists: {result > 0}")
            return result > 0

    logger.debug("About to check if model_version table exists")
    if not table_exists(engine, "model_version"):
        logger.debug("model_version table does not exist, creating it...")
        # Create table if it doesn't exist
        with engine.connect() as connection:
            logger.debug("Executing CREATE TABLE model_version")
            connection.execute(
                text(
                    """
                CREATE TABLE model_version (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(50) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            logger.debug("CREATE TABLE executed successfully")
            new_version = "1.0.0"
            logger.debug(f"Inserting version '{new_version}' into model_version table")
            connection.execute(
                text(f"INSERT INTO model_version (version) VALUES ('{new_version}');")
            )
            logger.debug("INSERT executed successfully")
            connection.commit()
            logger.debug("COMMIT executed successfully")
    else:
        logger.debug("DEBUG: model_version table exists, updating version...")
        # Get last version and increment minor version by 0.0.1
        with engine.connect() as connection:
            last_version = connection.execute(
                text("SELECT version FROM model_version ORDER BY id DESC LIMIT 1")
            ).scalar()
            major, minor, patch = map(int, last_version.split("."))
            new_version = f"{major}.{minor}.{patch + 1}"
            connection.execute(
                text(
                    "UPDATE model_version SET version = :version "
                    "WHERE id = (SELECT MAX(id) FROM model_version)"
                ),
                {"version": new_version},
            )
            connection.commit()

    minio_client = Minio(
        endpoint=os.getenv("MINIO_HOST", "endpoint") + ":" + os.getenv("MINIO_PORT", "9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "access-key"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "secret-key"),
        secure=False,  # Set to True if using HTTPS
    )

    bucket_name = "user-encoder"
    object_name = f"user-encoder-{new_version}.pth"
    configuration = f"user-encoder-config-{new_version}.json"

    # Ensure the bucket exists, create it if it doesn't
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    minio_client.fput_object(
        bucket_name=bucket_name,
        object_name=object_name,
        file_path=user_output_model.path,
    )
    # Save model configurations
    minio_client.fput_object(
        bucket_name=bucket_name,
        object_name=configuration,
        file_path=models_definition_output.path,
    )
    modelMetadata = NamedTuple(
        "modelMetadata",
        [
            ("bucket_name", str),
            ("new_version", str),
            ("object_name", str),
            ("torch_version", str),
        ],
    )
    return modelMetadata(bucket_name, new_version, object_name, torch.__version__[0:5])


@dsl.component(base_image="quay.io/rh-ai-quickstart/recommendation-oc-tools:latest")
def fetch_cluster_credentials() -> NamedTuple(
    "ocContext", [("author", str), ("user_token", str), ("host", str)]
):
    import os
    import subprocess
    from typing import NamedTuple
    import logging

    logger = logging.getLogger(__name__)

    author_value = subprocess.run(
        "oc whoami", shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()
    user_token_value = subprocess.run(
        "oc whoami -t", shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()
    logger.debug(f"author_value = {author_value}")
    mr_namespace = os.getenv("MODEL_REGISTRY_NAMESPACE", "rhoai-model-registries")
    mr_container = os.getenv("MODEL_REGISTRY_CONTAINER", "modelregistry-sample")

    cmd = (
        f"oc get svc {mr_container} -n {mr_namespace} -o json | "
        f"jq '.metadata.annotations.\"routing.opendatahub.io/external-address-rest\"'"
    )
    host_output = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()

    if not host_output:
        error_message = (f"Model registry service '{mr_container}' is not available in namespace '{mr_namespace}'. "
                         f"Please ensure the service is properly deployed and accessible.")
        logger.info(error_message)
        raise RuntimeError(error_message)

    host_value = f"https://{host_output[1:-5]}"  # Remove quotes and :443

    ocContext = NamedTuple("ocContext", [("author", str), ("user_token", str), ("host", str)])
    return ocContext(author_value, user_token_value, host_value)


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["model_registry"])
def registry_model_to_model_registry(
    author: str,
    user_token: str,
    host: str,
    bucket_name: str,
    new_version: str,
    object_name: str,
    torch_version: str,
):
    import os
    from datetime import datetime

    from model_registry import ModelRegistry, utils

    registry = ModelRegistry(host, author=author, user_token=user_token)
    # Use DNS with the namespace 'rhoai-model-registries'
    model_endpoint = f"https://{host}:{os.environ.get('MINIO_PORT')}"

    registry.register_model(
        name="item-encoder",
        uri=utils.s3_uri_from(
            endpoint=model_endpoint,
            bucket=bucket_name,
            path=object_name,
            region=os.environ.get("REGION", "us-east-1"),
        ),
        version=(f"{new_version}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"),
        model_format_name="pytorch",
        model_format_version=torch_version,
        storage_key="minio",
    )


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["psycopg2-binary"])
def load_data_from_feast(
    item_df_output: Output[Dataset],
    user_df_output: Output[Dataset],
    interaction_df_output: Output[Dataset],
):
    import os
    import subprocess

    import pandas as pd
    import tabulate as tb
    from feast import FeatureStore
    from recommendation_core.service.dataset_provider import (
        LocalDatasetProvider,
        RemoteDatasetProvider,
    )
    from sqlalchemy import create_engine, text
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    logger.info("Starting load_data_from_feast")

    with open("src/recommendation_core/feature_repo/feature_store.yaml", "r") as file:
        logger.info(file.read())
    store = FeatureStore(repo_path="src/recommendation_core/feature_repo/")
    store.refresh_registry()
    logger.info("registry refreshed")

    dataset_url = os.getenv("DATASET_URL", None)
    logger.info(f"DATASET_URL: {dataset_url}")
    if dataset_url is not None and dataset_url != "":
        logger.info("using custom remote dataset")
        # with force_load true, to align the parquet files
        dataset_provider = RemoteDatasetProvider(dataset_url, force_load=True)
    else:
        logger.info("using pre generated dataset")
        dataset_provider = LocalDatasetProvider(store)

    # retrieve datasets for training
    item_df = dataset_provider.item_df()
    user_df = dataset_provider.user_df()
    interaction_df = dataset_provider.interaction_df()

    uri = os.getenv("uri", None)
    engine = create_engine(uri)

    def table_exists(engine, table_name):
        query = text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :table_name"
        )
        with engine.connect() as connection:
            result = connection.execute(query, {"table_name": table_name}).scalar()
            return result > 0

    if table_exists(engine, "users"):
        query_users = "SELECT user_id, email as user_name, preferences, signup_date FROM users"
        try:
            stream_users_df = pd.read_sql(query_users, engine)
        except Exception as e:
            logger.error(f"Error reading users from database: {e}")
            stream_users_df = pd.DataFrame()


        logger.debug("Showing head of tables")
        logger.debug(f"stream_users_df: \n{tb.tabulate(stream_users_df.head(), headers='keys', tablefmt='grid')}")
        logger.debug("****************************************")
        logger.debug(f"user_df: \n{tb.tabulate(user_df.head(), headers='keys', tablefmt='grid')}")


        if not stream_users_df.empty:
            logger.debug(f"user_df columns: {user_df.columns}")
            logger.debug(f"stream_users_df columns: {stream_users_df.columns}")
            stream_users_df['signup_date'] = pd.to_datetime(stream_users_df['signup_date'])
            logger.info(f"Adding {len(stream_users_df)} users to user_df")
            user_df = pd.concat([user_df, stream_users_df], axis=0)
            logger.debug(f"user_df columns: {user_df.columns}")
        else:
            logger.info("No new users found in database")

    if table_exists(engine, "stream_interaction"):
        query_positive = "SELECT * FROM stream_interaction"
        try:
            stream_positive_inter_df = pd.read_sql(query_positive, engine).rename(
                columns={"timestamp": "event_timestamp"}
            )
        except Exception as e:
            logger.error(f"Error reading positive interactions from database: {e}")
            stream_positive_inter_df = pd.DataFrame()

        if not stream_positive_inter_df.empty:
            logger.info(f"Adding {len(stream_positive_inter_df)} positive interactions to interaction_df")
            interaction_df = pd.concat([interaction_df, stream_positive_inter_df], axis=0)
        else:
            logger.info("No new positive interactions found in database")

    # Pass artifacts
    logger.info("Saving artifacts to parquet files")
    item_df.to_parquet(item_df_output.path)
    user_df.to_parquet(user_df_output.path)
    logger.info(f"num of interactions: {len(interaction_df)}")
    interaction_df = interaction_df.head(5000)
    interaction_df.to_parquet(interaction_df_output.path)
    logger.info(
        f"Saved {len(item_df)} items for {len(user_df)} users with {len(interaction_df)} interactions"
    )

    item_df_output.metadata["format"] = "parquet"
    user_df_output.metadata["format"] = "parquet"
    interaction_df_output.metadata["format"] = "parquet"


def mount_secret_feast_repository(task):
    kubernetes.use_secret_as_env(
        task=task,
        secret_name=os.getenv("DB_SECRET_NAME", "cluster-sample-app"),
        secret_key_to_env={
            "uri": "uri",
            "password": "DB_PASSWORD",
            "host": "DB_HOST",
            "dbname": "DB_NAME",
            "user": "DB_USER",
            "port": "DB_PORT",
        },
    )
    kubernetes.use_secret_as_volume(
        task=task,
        secret_name=os.getenv("FEAST_SECRET_NAME", "feast-feast-recommendation-registry-tls"),
        mount_path="/app/feature_repo/secrets",
    )
    task.set_env_variable(
        name="FEAST_PROJECT_NAME",
        value=os.getenv("FEAST_PROJECT_NAME", "feast_rec_sys"),
    )
    task.set_env_variable(
        name="FEAST_REGISTRY_URL",
        value=os.getenv(
            "FEAST_REGISTRY_URL",
            "feast-feast-recommendation-registry.recommendation.svc.cluster.local",
        ),
    )
    dataset_url = os.getenv("DATASET_URL")
    if dataset_url is not None:
        task.set_env_variable(name="DATASET_URL", value=dataset_url)


@dsl.pipeline(name=os.path.basename(__file__).replace(".py", ""))
def batch_recommendation():
    load_data_task = load_data_from_feast()
    mount_secret_feast_repository(load_data_task)
    # Component configurations
    load_data_task.set_caching_options(False)

    # setting resource requests and limits - TODO: use from environment variables
    load_data_task.set_cpu_request("2000m")
    load_data_task.set_memory_request("2000Mi")
    load_data_task.set_cpu_limit("3000m")
    load_data_task.set_memory_limit("3000Mi")

    fetch_api_credentials_task = fetch_cluster_credentials()

    fetch_api_credentials_task.set_caching_options(
        False
    )  # if set to true, the task will be cached and the credentials will not be updated.

    fetch_api_credentials_task.set_env_variable(
        name="MODEL_REGISTRY_NAMESPACE", value=os.getenv("MODEL_REGISTRY_NAMESPACE", "rhoai-model-registries")
    )
    fetch_api_credentials_task.set_env_variable(
        name="MODEL_REGISTRY_CONTAINER", value=os.getenv("MODEL_REGISTRY_CONTAINER", "modelregistry-sample")
    )

    train_model_task = train_model(
        item_df_input=load_data_task.outputs["item_df_output"],
        user_df_input=load_data_task.outputs["user_df_output"],
        interaction_df_input=load_data_task.outputs["interaction_df_output"],
    ).after(load_data_task)

    # setting resource requests and limits - TODO: use from environment variables
    train_model_task.set_cpu_request("2000m")
    train_model_task.set_memory_request("2000Mi")
    train_model_task.set_cpu_limit("3000m")
    train_model_task.set_memory_limit("3000Mi")

    train_model_task.set_caching_options(False)
    kubernetes.use_secret_as_env(
        task=train_model_task,
        secret_name=os.getenv("MINIO_SECRET_NAME", "ds-pipeline-s3-dspa"),
        secret_key_to_env={
            "host": "MINIO_HOST",
            "port": "MINIO_PORT",
            "accesskey": "MINIO_ACCESS_KEY",
            "secretkey": "MINIO_SECRET_KEY",
            "secure": "MINIO_SECURE",
        },
    )
    kubernetes.use_secret_as_env(
        task=train_model_task,
        secret_name=os.getenv("DB_SECRET_NAME", "cluster-sample-app"),
        secret_key_to_env={
            "uri": "uri",
        },
    )

    create_model_registry_task = registry_model_to_model_registry(
        author=fetch_api_credentials_task.outputs["author"],
        user_token=fetch_api_credentials_task.outputs["user_token"],
        host=fetch_api_credentials_task.outputs["host"],
        bucket_name=train_model_task.outputs["bucket_name"],
        new_version=train_model_task.outputs["new_version"],
        object_name=train_model_task.outputs["object_name"],
        torch_version=train_model_task.outputs["torch_version"],
    ).after(train_model_task, fetch_api_credentials_task)
    create_model_registry_task.set_caching_options(False)
    kubernetes.use_secret_as_env(
        task=create_model_registry_task,
        secret_name=os.getenv("MINIO_SECRET_NAME", "ds-pipeline-s3-dspa"),
        secret_key_to_env={
            "host": "MINIO_HOST",
            "port": "MINIO_PORT",
        },
    )

    # setting resource requests and limits - TODO: use from environment variables
    create_model_registry_task.set_cpu_request("2000m")
    create_model_registry_task.set_memory_request("2000Mi")
    create_model_registry_task.set_cpu_limit("3000m")
    create_model_registry_task.set_memory_limit("3000Mi")

    generate_candidates_task = generate_candidates(
        item_input_model=train_model_task.outputs["item_output_model"],
        user_input_model=train_model_task.outputs["user_output_model"],
        item_df_input=load_data_task.outputs["item_df_output"],
        user_df_input=load_data_task.outputs["user_df_output"],
        models_definition_input=train_model_task.outputs["models_definition_output"],
    ).after(train_model_task)
    kubernetes.use_secret_as_env(
        task=generate_candidates_task,
        secret_name=os.getenv("DB_SECRET_NAME", "cluster-sample-app"),
        secret_key_to_env={
            "uri": "uri",
            "password": "DB_PASSWORD",
            "host": "DB_HOST",
            "dbname": "DB_NAME",
            "user": "DB_USER",
            "port": "DB_PORT",
        },
    )
    kubernetes.use_secret_as_volume(
        task=generate_candidates_task,
        secret_name=os.getenv("FEAST_SECRET_NAME", "feast-feast-edb-recommendation-registry-tls"),
        mount_path="/app/feature_repo/secrets",
    )
    generate_candidates_task.set_env_variable(
        name="FEAST_PROJECT_NAME",
        value=os.getenv("FEAST_PROJECT_NAME", "feast_edb_rec_sys"),
    )
    generate_candidates_task.set_env_variable(
        name="FEAST_REGISTRY_URL",
        value=os.getenv(
            "FEAST_REGISTRY_URL",
            "feast-feast-edb-recommendation-registry.recommendation.svc.cluster.local",
        ),
    )
    generate_candidates_task.set_caching_options(False)

    # setting resource requests and limits - TODO: use from environment variables    # setting resource requests and limits - TODO: use from environment variables
    generate_candidates_task.set_cpu_request("2000m")
    generate_candidates_task.set_memory_request("2000Mi")
    generate_candidates_task.set_cpu_limit("3000m")
    generate_candidates_task.set_memory_limit("3000Mi")



if __name__ == "__main__":
    pipeline_yaml = __file__.replace(".py", ".yaml")

    compiler.Compiler().compile(pipeline_func=batch_recommendation, package_path=pipeline_yaml)

    client = Client(host=os.environ["DS_PIPELINE_URL"], verify_ssl=False)

    pipelines = client.list_pipelines().pipelines
    pipeline_name = os.environ["PIPELINE_NAME"]
    pipeline_exists = (
        False if pipelines is None else any(p.display_name == pipeline_name for p in pipelines)
    )
    if not pipeline_exists:
        uploaded_pipeline = client.upload_pipeline(
            pipeline_package_path=pipeline_yaml, pipeline_name=pipeline_name
        )

    run = client.create_run_from_pipeline_package(
        pipeline_file=pipeline_yaml, arguments={}, run_name=os.environ["RUN_NAME"]
    )

    logger.info(f"Pipeline submitted! Run ID: {run.run_id}")
