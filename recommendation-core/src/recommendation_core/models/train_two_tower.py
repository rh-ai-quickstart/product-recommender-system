import logging

import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from recommendation_core.models.data_util import (UserItemMagnitudeDataset,
                                                  preprocess_pipeline)
from recommendation_core.models.entity_tower import EntityTower
from recommendation_core.models.two_tower import TwoTowerModel

logger = logging.getLogger(__name__)


def create_and_train_two_tower(
    items_df: pd.DataFrame,
    users_df: pd.DataFrame,
    interactions_df: pd.DataFrame,
    return_epoch_losses: bool = False,
    n_epochs: int = 10,
    return_model_definition: bool = False,
):
    dataset = preprocess_pipeline(items_df, users_df, interactions_df)
    models_definition = {
        "items_num_numerical": dataset.items_num_numerical,
        "items_num_categorical": 0,
        #"items_num_categorical": dataset.items_num_categorical,
        "users_num_numerical": dataset.users_num_numerical,
        "users_num_categorical": 0,
        #"users_num_categorical": dataset.users_num_categorical,
    }
    #item_tower = EntityTower(dataset.items_num_numerical, dataset.items_num_categorical)
    #user_tower = EntityTower(dataset.users_num_numerical, dataset.users_num_categorical)
    item_tower = EntityTower(dataset.items_num_numerical, 0)
    user_tower = EntityTower(dataset.users_num_numerical, 0)

    two_tower_model = TwoTowerModel(item_tower, user_tower)

    epoch_losses = _train(dataset, two_tower_model, n_epochs=n_epochs)
    if return_epoch_losses and return_model_definition:
        return item_tower, user_tower, epoch_losses, models_definition
    if return_model_definition:
        return item_tower, user_tower, models_definition
    if return_epoch_losses:
        return item_tower, user_tower, epoch_losses

    return item_tower, user_tower


def train_two_tower(
    item_tower: EntityTower,
    user_tower: EntityTower,
    items_df: pd.DataFrame,
    users_df: pd.DataFrame,
    interactions_df_pos: pd.DataFrame,
    return_epoch_losses: bool = False,
    n_epochs: int = 10,
):

    dataset = preprocess_pipeline(items_df, users_df, interactions_df_pos)
    two_tower_model = TwoTowerModel(item_tower, user_tower)

    epoch_losses = _train(dataset, two_tower_model, n_epochs=n_epochs)
    if return_epoch_losses:
        return epoch_losses


def _train(
    dataset: UserItemMagnitudeDataset,
    two_tower_model: TwoTowerModel,
    n_epochs: int = 10,
    device: str = "cpu",
    batch_size: int = 256,
):
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Define optimizer and loss function
    optimizer = torch.optim.Adam(two_tower_model.parameters(), lr=0.001)
    criterion = nn.MSELoss()  # Assuming magnitude prediction is a regression task

    # Set model to training mode
    two_tower_model.to(device)
    two_tower_model.train()

    # Store losses for each epoch
    epoch_losses = []

    # Training loop over epochs
    for epoch in range(n_epochs):
        total_loss = 0.0
        num_batches = 0

        for items, users, magnitude in dataloader:
            # Move data to specified device
            items = {
                key: value.to(device) if type(value) == torch.Tensor else value
                for key, value in items.items()
            }
            users = {
                key: value.to(device) if type(value) == torch.Tensor else value
                for key, value in users.items()
            }
            magnitude = magnitude.to(device)

            # Zero the gradients
            optimizer.zero_grad()

            # Forward pass
            predictions = two_tower_model(items, users)

            # Calculate loss
            loss = criterion(predictions, magnitude)

            # Backward pass and optimize
            loss.backward()
            optimizer.step()

            # Track loss
            total_loss += loss.item()
            num_batches += 1

        # Calculate and store average loss for the epoch
        avg_loss = total_loss / num_batches
        epoch_losses.append(avg_loss)

        # Optional: Print progress
        logger.info(f"Epoch {epoch+1}/{n_epochs}, Average Loss: {avg_loss:.4f}")

    return epoch_losses
