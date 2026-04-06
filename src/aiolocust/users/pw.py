from contextlib import asynccontextmanager

from opentelemetry import trace
from playwright.async_api import Page, async_playwright  # pyright: ignore[reportMissingImports]

from aiolocust import User, stats
from aiolocust.datatypes import Request
from aiolocust.runner import Runner

# Setup OTel Tracer (this is probably going to need to change)
tracer = trace.get_tracer("playwright-instrumentation")

playwright_instance = None
browser_instance = None


class LocustPage:
    """A wrapper for the Playwright Page object to automatically generate OTel spans."""

    def __init__(self, page: Page):
        self._page = page

    async def goto(self, url: str, **kwargs):
        with tracer.start_as_current_span("playwright.goto") as span:
            span.set_attribute("browser.url", url)
            try:
                result = await self._page.goto(url, **kwargs)
                stats.request(Request(url, 1, 1, None))
            except Exception as e:
                span.record_exception(e)
                stats.request(Request(url, 1, 1, e))
                raise
            return result

    async def click(self, selector: str, **kwargs):
        with tracer.start_as_current_span("playwright.click") as span:
            span.set_attribute("browser.selector", selector)
            try:
                result = await self._page.click(selector, **kwargs)
                stats.request(Request(selector, 1, 1, None))
            except Exception as e:
                span.record_exception(e)
                stats.request(Request(selector, 1, 1, e))
                raise
            return result


class PlaywrightUser(User):
    def __init__(self, runner: Runner | None = None, **kwargs):
        super().__init__(runner)
        self.kwargs = kwargs
        self.page: LocustPage  # type: ignore[assignment] # always set in cm

    @asynccontextmanager
    async def cm(self):
        global playwright_instance, browser_instance
        if playwright_instance is None:
            playwright_instance = await async_playwright().start()
            browser_instance = await playwright_instance.chromium.launch(
                headless=False,  # Probably wanna set this to true later on
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
                handle_sigint=False,
            )
        assert browser_instance
        context = await browser_instance.new_context()
        raw_page = await context.new_page()
        self.page = LocustPage(raw_page)

        yield

        await raw_page.close()
        await context.close()
