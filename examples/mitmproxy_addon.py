# To generate a locustfile based on live traffic.
#
# 1. Install mitmproxy & trust its certificate authority:
#    brew install --cask mitmproxy
#    sudo security add-trusted-cert -d -p ssl -p basic -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
# 2. Start the proxy:
#    mitmdump -s examples/mitmproxy_addon.py
# 3. Use the proxy from your browser or app. For example, using curl:
#    curl -x http://localhost:8080 -k https://www.google.com
# Or using Chrome:
#    open -na "Google Chrome" --args --incognito --proxy-server="http://127.0.0.1:8080" --user-data-dir="/tmp/chrome-proxy-session" --no-first-run --no-default-browser-check --disable-component-update --disable-extensions --new-window --proxy-bypass-list="<-loopback>" http://localhost/some-url
# 4. Look at the generated locustfile.py!

from mitmproxy import http  # type: ignore

ignored_urls = [
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

# These are created by aiohttp anyway
ignored_headers = ["user-agent", "content-length", "cookie"]


class AioExporter:
    def __init__(self):
        self.filename = "locustfile.py"
        with open(self.filename, "w") as f:
            f.write(
                """from aiolocust import HttpUser


async def run(self: HttpUser):
"""
            )

    def request(self, flow: http.HTTPFlow):
        method: str = flow.request.method.lower()
        url: str = flow.request.url
        headers = dict(flow.request.headers)

        for ignored_header in ignored_headers:
            if ignored_header in headers:
                del headers[ignored_header]

        for ignored_url in ignored_urls:
            if url.startswith(ignored_url):
                print(f"Skipping {url} since it starts with {ignored_url}")
                return
        with open(self.filename, "a") as f:
            f.write(f"""    async with self.client.{method}("{url}", headers={headers}) as resp:
        pass\n""")


addons = [AioExporter()]
