from contextlib import asynccontextmanager

from opentelemetry import trace
from playwright.async_api import Page, async_playwright  # pyright: ignore[reportMissingImports]

from aiolocust import User, stats
from aiolocust.datatypes import Request
from aiolocust.runner import Runner

# Setup OTel Tracer (this is probably going to need to change)
tracer = trace.get_tracer("playwright-instrumentation")


class LocustPage:
    """A wrapper for the Playwright Page object to automatically generate OTel spans."""

    def __init__(self, page: Page):
        self._page = page

    async def goto(self, url: str, **kwargs):
        with tracer.start_as_current_span("playwright.goto") as span:
            span.set_attribute("browser.url", url)
            try:
                result = await self._page.goto(url, **kwargs)
                stats.request(Request(url, 42, 42, None))
            except Exception as e:
                span.record_exception(e)
                stats.request(Request(url, 42, 42, e))
                raise
            return result

    async def click(self, selector: str, **kwargs):
        with tracer.start_as_current_span("playwright.click") as span:
            span.set_attribute("browser.selector", selector)
            try:
                result = await self._page.click(selector, **kwargs)
                stats.request(Request(selector, 42, 42, None))
            except Exception as e:
                span.record_exception(e)
                stats.request(Request(selector, 42, 42, e))
                raise
            return result


class PlaywrightUser(User):
    def __init__(self, runner: Runner | None = None, **kwargs):
        super().__init__(runner)
        self.kwargs = kwargs
        self.client: LocustPage  # type: ignore[assignment] # always set in cm

    @asynccontextmanager
    async def cm(self):
        async with async_playwright() as p:  # this is probably silly, we should not have one pw instance per User
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--safebrowsing-disable-auto-update",
                    "--disable-sync",
                    "--hide-scrollbars",
                    "--disable-notifications",
                    "--disable-logging",
                    "--ignore-certificate-errors",
                    "--no-first-run",
                    "--disable-audio-output",
                    "--disable-canvas-aa",
                    "--lang=en-US",
                    "--disable-features=LanguageDetection",
                ],
            )
            context = await browser.new_context()
            raw_page = await context.new_page()
            self.client = LocustPage(raw_page)
            yield
            await browser.close()
