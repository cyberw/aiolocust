# How to iterate over mongodb documents in LRU order, useful for getting test data (e.g. customers)
import json
import logging
import os
from collections.abc import AsyncIterator

# Use threading.Lock because asyncio.Lock is not cross-loop safe
from threading import Lock

import pymongo
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.cursor import AsyncCursor

from aiolocust import HttpUser, Runner

logger = logging.getLogger(__name__)
dblock = Lock()


class MongoLRUReader(AsyncIterator[dict]):
    def __init__(self, coll: AsyncCollection, filter: dict | None = None, timestamp_field: str = "last_used"):
        self.timestamp_field = timestamp_field
        self.coll = coll
        self.filter = filter or {}
        self.cursor: AsyncCursor = self.coll.find(filter).sort(self.timestamp_field, pymongo.ASCENDING)

    async def __anext__(self) -> dict:
        with dblock:
            doc: dict
            try:
                doc = await self.cursor.next()
            except StopAsyncIteration:
                await self.cursor.rewind()
                try:
                    doc = await self.cursor.next()
                except StopAsyncIteration:
                    raise Exception(f"cursor had no docs, maybe your filter ({self.filter}) is bad?")
            await self.coll.update_one(
                {"_id": doc["_id"]},
                {"$currentDate": {self.timestamp_field: True}},
            )
            return doc


client = AsyncMongoClient(os.environ["MONGO_URI"])
coll = client[os.environ["MONGO_DB"]][os.environ["MONGO_COLLECTION"]]
filter = json.loads(os.getenv("MONGO_FILTER", "{}"))
mlr = MongoLRUReader(coll, filter)


class MyUser(HttpUser):
    async def run(self: HttpUser):
        ssn = (await anext(mlr))["ssn"]
        async with self.client.get(f"http://localhost:8080/{ssn}") as resp:
            pass


if __name__ == "__main__":
    Runner([MyUser], 1, iterations=4).run_test()
