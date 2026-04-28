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


async def iter_docs(
    coll: AsyncCollection,
    filter: dict | None = None,
    timestamp_field: str = "last_used",
) -> AsyncIterator[dict]:
    """Thread safe and looping wrapper for coll.filter() / AsyncCursor suitable for test data like customers."""
    filter = filter or {}
    cursor: AsyncCursor = coll.find(filter).sort(timestamp_field, pymongo.ASCENDING)
    while True:
        with dblock:
            doc: dict
            try:
                doc = await cursor.next()
            except StopAsyncIteration:
                await cursor.rewind()
                try:
                    doc = await cursor.next()
                except StopAsyncIteration:
                    raise Exception(f"cursor had no docs, maybe your filter ({filter}) is bad?")
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$currentDate": {timestamp_field: True}},
            )
            yield doc


client = AsyncMongoClient(os.environ["MONGO_URI"])
coll = client[os.environ["MONGO_DB"]][os.environ["MONGO_COLLECTION"]]
filter = json.loads(os.getenv("MONGO_FILTER", "{}"))
customers = iter_docs(coll, filter)


class MyUser(HttpUser):
    async def run(self: HttpUser):
        ssn = (await anext(customers))["ssn"]
        async with self.client.get(f"http://localhost:8080/{ssn}") as resp:
            pass


if __name__ == "__main__":
    Runner([MyUser], 1, iterations=4).run_test()
