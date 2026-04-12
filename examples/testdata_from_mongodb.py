# How to iterate over mongodb documents in LRU order, useful for getting test data (e.g. customers)
import logging
from collections.abc import AsyncIterator

# Use threading.Lock because asyncio.Lock is not cross-loop safe
from threading import Lock

import pymongo
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.cursor import AsyncCursor

from aiolocust import HttpUser, Runner

logger = logging.getLogger(__name__)


class MongoLRUReader(AsyncIterator[dict]):
    def __init__(self, coll: AsyncCollection, filter: dict | None = None, timestamp_field: str = "last_used"):
        self.timestamp_field = timestamp_field
        self.coll = coll
        self.cursor: AsyncCursor = self.coll.find(filter or {}).sort(self.timestamp_field, pymongo.ASCENDING)
        records_in_buffer = self.cursor._refresh()  # trigger fetch immediately instead of waiting for the first next()
        if not records_in_buffer:
            logger.warning(f"No records returned from query {filter}")

    async def __anext__(self) -> dict:
        with dblock:
            doc: dict
            try:
                doc = await self.cursor.next()
            except StopAsyncIteration:
                await self.cursor.rewind()
                doc = await self.cursor.next()
            await self.coll.update_one(
                {"_id": doc["_id"]},
                {"$currentDate": {self.timestamp_field: True}},
            )
            return doc


client = AsyncMongoClient("mongodb://localhost:27017")
coll = client["sample_db"]["inventory"]
mlr = MongoLRUReader(coll, {"qty": {"$gt": 1}})
dblock = Lock()


class MyUser(HttpUser):
    async def run(self: HttpUser):
        doc = await anext(mlr)
        async with self.client.get(f"http://localhost:8080/{doc['item']}") as resp:
            pass


if __name__ == "__main__":
    Runner([MyUser], 1, iterations=4).run_test()
