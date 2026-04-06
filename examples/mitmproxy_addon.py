# Used to generate a locustfile based on live traffic, using mitmproxy.
#
# It supports a couple different options, but the easiest use case is just:
# mitmdump -s examples/mitmproxy_addon.py

import os
from datetime import datetime

# this script is meant to be imported from mitmproxy, not run using aiolocust, so type checking wouldn't work
from mitmproxy import http  # type: ignore

IGNORED_URLS = os.getenv(
    "LOCUST_IGNORED_URLS",
    # These are created by chrome at startup and are almost never relevant:
    "https://www.google.com/async,https://optimizationguide-pa.googleapis.com,https://safebrowsing.googleapis.com/,https://android.clients.google.com,https://accounts.google.com/,http://clients2.google.com/,https://update.googleapis.com/,https://pagead2.googlesyndication.com/,https://clientservices.googleapis.com/",
).split(",")
if extra_urls := os.getenv("LOCUST_EXTRA_IGNORED_URLS"):
    IGNORED_URLS.extend(extra_urls.split(","))

IGNORED_HEADERS = os.getenv(
    "LOCUST_IGNORED_HEADERS",
    # These are created by aiohttp automatically so they don't need to be in the script:
    "user-agent,content-length,cookie,host",
).split(",")
if extra_headers := os.getenv("LOCUST_EXTRA_IGNORED_HEADERS"):
    IGNORED_HEADERS.extend(extra_headers.lower().split(","))  # headers are case-insensitive
print(IGNORED_HEADERS)

IGNORED_METHODS = os.getenv("LOCUST_IGNORED_METHODS", "options").split(",")


class LocustExporter:
    def __init__(self):
        self.filename = os.getenv("LOCUST_LOCUSTFILE", "locustfile.py")
        self.new_file()

    def new_file(self):
        with open(self.filename, "w") as f:
            f.write(
                f"""# This file was generated using mitmproxy at {datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
from aiolocust import HttpUser


async def run(self: HttpUser):
"""
            )

    def response(self, flow: http.HTTPFlow):
        method: str = flow.request.method.lower()
        url: str = flow.request.url
        headers = dict(flow.request.headers)

        for header in headers.copy():
            if header.lower() in IGNORED_HEADERS:
                del headers[header]

        for ignored_url in IGNORED_URLS:
            if url.startswith(ignored_url):
                print(f"Skipping {url} since it starts with {ignored_url}")
                return

        if method in IGNORED_METHODS:
            return

        if not os.path.isfile(self.filename):
            # in case someone deleted the file while mitmproxy was running
            self.new_file()

        with open(self.filename, "a") as f:
            f.write(f"""    async with self.client.{method}("{url}", headers={headers}) as resp:
        pass\n""")


addons = [LocustExporter()]
