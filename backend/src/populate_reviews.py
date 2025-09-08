import asyncio

from init_backend import populate_reviews


if __name__ == "__main__":
    asyncio.run(populate_reviews())
