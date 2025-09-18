import torch
import torch.nn as nn
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

class ItemTower(nn.Module):
    def __init__(self, d_model=64, category_count=5, subcategory_count=25):
        super().__init__()
        logger.info("This is actually used!")
        
        # Define ratios for each feature.
        ratios = {
            "category": 3,
            "subcategory": 3,
            "price": 3,
            "avg_rating": 2,
            "num_ratings": 2,
            "popular": 1,
            "new_arrival": 1,
            "on_sale": 1,
            "arrival_date": 1,
        }
        total_ratio = sum(ratios.values())
        unit_dim = d_model // total_ratio
        dim_reminder = d_model % total_ratio

        # Define the dimention
        dims = {k: v * unit_dim for k, v in ratios.items()}
        # add the leftover dim to subcategory
        dims["subcategory"] = dims.get("subcategory") + dim_reminder

        # Create embedding modules for categorical features.
        self.embeds = nn.ModuleDict(
            {
                "category": nn.Embedding(category_count, dims["category"]),
                "subcategory": nn.Embedding(subcategory_count, dims["subcategory"]),
            }
        )

        # Define keys for numeric features.
        self.numeric_keys = [
            "price",
            "avg_rating",
            "num_ratings",
            "popular",
            "new_arrival",
            "on_sale",
            "arrival_date",
        ]

        # Create projection and normalization modules for each numeric feature.
        self.encoders = nn.ModuleDict(
            {k: nn.Linear(1, dims[k]) for k in self.numeric_keys}
        )
        self.norms = nn.ModuleDict({k: nn.RMSNorm(dims[k]) for k in self.numeric_keys})

        self.fn1 = nn.Linear(d_model, d_model * 2)
        self.fn2 = nn.Linear(d_model * 2, d_model)
        self.fn3 = nn.Linear(d_model, d_model * 2)
        self.fn4 = nn.Linear(d_model * 2, d_model)

        self.norm = nn.RMSNorm(d_model)
        self.norm1 = nn.RMSNorm(d_model)
        self.norm2 = nn.RMSNorm(d_model)

        self.relu = nn.ReLU()

    def forward(
        self,
        category,
        subcategory,
        price,
        avg_rating,
        num_ratings,
        popular,
        new_arrival,
        on_sale,
        arrival_date,
    ):
        # Process categorical features.
        cat_out = [
            self.embeds["category"](category),
            self.embeds["subcategory"](subcategory),
        ]
        # Process numeric features using a loop.
        num_inputs = [
            price,
            avg_rating,
            num_ratings,
            popular,
            new_arrival,
            on_sale,
            arrival_date,
        ]
        num_out = [
            self.norms[k](self.encoders[k](x))
            for k, x in zip(self.numeric_keys, num_inputs)
        ]
        # Concatenate all feature representations.
        x = torch.cat(cat_out + num_out, dim=-1)

        x = self.norm(x)
        y = self.relu(self.fn1(self.norm1(x)))
        x = self.relu(self.fn2(y)) + x
        # y = self.relu(self.fn1(self.norm2(x)))
        # x = self.relu(self.fn2(y)) + x
        return x


# import torch
# import torch.nn as nn
# from torch import Tensor


# class ItemTower(nn.Module):
#     def __init__(self, num_numerical: int, num_of_categories: int, numerical_dim: int, d_model: int=64):
#         super().__init__()
#         categorical_dim = d_model - numerical_dim

#         # Create embedding modules for categorical features.
#         self.categorical_embed = nn.Embedding(num_of_categories, categorical_dim)

#         # Create projection and normalization modules for each numeric feature.
#         self.numeric_norm = nn.BatchNorm1d(num_numerical)
#         self.numeric_embed = nn.Linear(num_numerical, numerical_dim)

#         self.fn1 = nn.Linear(d_model, d_model * 2)
#         self.fn2 = nn.Linear(d_model * 2, d_model)

#         self.norm = nn.RMSNorm(d_model)
#         self.norm1 = nn.RMSNorm(d_model)

#         self.relu = nn.ReLU()

#     def forward(self, x_numeric: Tensor, x_categorical: Tensor):
#         # Process categorical features.
#         x_numeric = self.numeric_embed(self.numeric_norm(x_numeric))
#         # Process numeric features using a loop.
#         num_inputs = self.categorical_embed(x_categorical)
#         # Concatenate all feature representations.
#         x = torch.cat([x_numeric, num_inputs], dim=-1)

#         x = self.norm(x)
#         y = self.relu(self.fn1(self.norm1(x)))
#         x = self.relu(self.fn2(y)) + x
#         return x
