# To generate a locustfile based on live traffic.
#
# 1. Install mitmproxy & trust its certificate authority:
#    brew install --cask mitmproxy
#    sudo security add-trusted-cert -d -p ssl -p basic -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
#
# 2. Start the proxy:
#    mitmdump -s examples/mitmproxy_addon.py
#
# 3. Use the proxy from your browser or app.
# Using curl:
#    curl -x http://localhost:8080 -k https://www.google.com
# Using Chrome:
#    open -na "Google Chrome" --args --incognito --proxy-server="http://127.0.0.1:8080" --user-data-dir="/tmp/chrome-proxy-session" --no-first-run --no-default-browser-check --disable-component-update --disable-extensions --new-window --proxy-bypass-list="<-loopback>" http://localhost/some-url
#    ... and click around doing your stuff!
# You can of course use any app, and you can configure the proxy settings on OS level or within the app if it supports that.
#
# 4. Look at the generated locustfile.py (it is updated while recording)
#
# Feel free to tweak this script but you don't really need to understand it to use it.

import os.path
from datetime import datetime

from mitmproxy import http  # type: ignore

IGNORED_URLS = [
    "https://www.google.com/async",
    "https://optimizationguide-pa.googleapis.com",
    "https://safebrowsing.googleapis.com/",
    "https://android.clients.google.com",
    "https://accounts.google.com/",
    "http://clients2.google.com/",
    "https://update.googleapis.com/",
    "https://pagead2.googlesyndication.com/",
    "https://clientservices.googleapis.com/",
]

# These are created by aiohttp automatically so they don't need to be in the script
IGNORED_HEADERS = ["user-agent", "content-length", "cookie", "host"]


class LocustExporter:
    def __init__(self):
        self.filename = "locustfile.py"
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

        if not os.path.isfile(self.filename):
            # in case someone deleted the file while mitmproxy was running
            self.new_file()

        with open(self.filename, "a") as f:
            f.write(f"""    async with self.client.{method}("{url}", headers={headers}) as resp:
        pass\n""")


addons = [LocustExporter()]
