"""
ETag store implementations.

InMemoryETagStore  — dev/testing, state lost between runs (defined in fetcher.py,
                     re-exported here for convenience)
DynamoDBETagStore  — production, persists across Lambda cold starts

Both satisfy the ETagStore protocol defined in fetcher.py.
"""

from __future__ import annotations

import asyncio

import boto3

# Single source of truth lives alongside the ETagStore protocol in fetcher.py.
from scraper.fetcher import InMemoryETagStore  # noqa: F401  (re-exported)


class DynamoDBETagStore:
    """
    Persists ETags in DynamoDB so Lambda warm/cold starts both benefit
    from conditional GETs.

    Table schema:
        PK  url   (S)  — full URL
        Attr etag  (S)  — last seen ETag value
    """

    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    async def get(self, url: str) -> str | None:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._table.get_item(Key={"url": url}),
        )
        return response.get("Item", {}).get("etag")

    async def set(self, url: str, etag: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._table.put_item(Item={"url": url, "etag": etag}),
        )
