from datetime import datetime

import requests
import torch
from PIL import Image
from transformers import CLIPImageProcessor, CLIPModel, CLIPTokenizer

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
CLIP_MODEL_SIZE = 512


def open_image(url):
    try:
        return Image.open(requests.get(url, stream=True).raw)
    except Exception:
        return None


class ClipEncoder:
    def __init__(self):
        self.image_processor = CLIPImageProcessor.from_pretrained(CLIP_MODEL_NAME)
        self.tokenizer = CLIPTokenizer.from_pretrained(CLIP_MODEL_NAME)
        self.model = CLIPModel.from_pretrained(CLIP_MODEL_NAME)
        self.model.eval()

    def clip_embeddings(self, item_df):
        result = item_df[["item_id"]].copy()
        result["clip_latent_space_embedding"] = self.create_clip_embeddings(item_df)
        result["event_timestamp"] = datetime.now()
        return result

    def create_clip_embeddings(self, item_df):
        texts = item_df["about_product"].tolist()
        image_links = item_df["img_link"].tolist()
        images = [open_image(url) if url is not None else None for url in image_links]
        return self.encode_texts_and_images(texts, images)

    def encode_texts_and_images(
        self, texts: list[str], images: list[Image], batch_size: int = 32
    ):
        assert len(texts) == len(images)
        text_embeddings = self.encode_texts_batched(texts, batch_size=batch_size)
        image_embeddings, _ = self.encode_images_batched_having_nones(
            images, batch_size=batch_size
        )
        # image_embeddings can be null if the image is not present
        #   in this case: combined_embeddings == text_embeddings
        combined_embeddings = (image_embeddings * 2) + text_embeddings
        # we don't need to divide by 3, since we normalize them
        return (
            torch.nn.functional.normalize(combined_embeddings, p=2, dim=1)
            .cpu()
            .detach()
            .numpy()
            .tolist()
        )

    def encode_texts_batched(self, texts: list[str], batch_size: int = 32):
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.encode_texts(batch)
            all_embeddings.append(embeddings)
        return torch.cat(all_embeddings, dim=0)

    def encode_images_batched_having_nones(
        self, images: list[Image], batch_size: int = 32
    ):
        all_embeddings = []
        all_none_indices = []
        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]
            embeddings, none_indices = self.encode_images_having_nones(batch)
            all_none_indices.extend([x + i for x in none_indices])
            all_embeddings.append(embeddings)
        return torch.cat(all_embeddings, dim=0), all_none_indices

    def encode_images_having_nones(self, images: list[Image]):
        # Separate valid images and None values
        valid_images = []
        none_indices = []
        batch_size = len(images)

        for i, image in enumerate(images):
            if image is None:
                none_indices.append(i)
            else:
                valid_images.append(image)

        # If all texts are None, return empty tensors with proper shape
        if not valid_images:
            return torch.zeros((batch_size, CLIP_MODEL_SIZE)), none_indices

        valid_embeddings = self.encode_images(valid_images)
        # If there were no None values, return as is
        if not none_indices:
            return valid_embeddings, none_indices

        result = torch.zeros((batch_size, CLIP_MODEL_SIZE))
        # Fill valid tokenized results
        valid_idx = 0
        for i in range(batch_size):
            if i not in none_indices:
                result[i] = valid_embeddings[valid_idx]
                valid_idx += 1

        return result, none_indices

    def encode_texts(self, texts: list[str]):
        inputs = self.tokenizer(
            texts, padding=True, return_tensors="pt", truncation=True
        )
        with torch.inference_mode():
            return self.model.get_text_features(**inputs)

    def encode_images(self, images: list[Image]):
        inputs = self.image_processor(images, return_tensors="pt")
        with torch.inference_mode():
            return self.model.get_image_features(**inputs)
