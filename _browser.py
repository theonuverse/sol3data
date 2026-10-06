from pathlib import Path
from typing import Self

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from playwright_stealth import Stealth


class BrowserSession:
    """Own a Playwright browser and provide pages to the scraper classes.

    A session starts lazily on the first request, so both ``Characters().get(...)``
    and the explicit ``start``/``close`` lifecycle are supported.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        slow_mo: float = 0,
        devtools: bool = False,
        pause_on_open: bool = False,
        trace_path: str | Path | None = None,
    ) -> None:
        self.headless = headless
        self.slow_mo = slow_mo
        self.devtools = devtools
        self.pause_on_open = pause_on_open
        self.trace_path = Path(trace_path) if trace_path is not None else None
        self._stealth_ctx = Stealth().use_sync(sync_playwright())
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._tracing_started = False

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        self.close()

    def start(self) -> Self:
        """Start the browser if it is not already running."""
        if self._context is not None:
            return self
        if (self.devtools or self.pause_on_open) and self.headless:
            raise ValueError("devtools and pause_on_open require headless=False.")

        pw = self._stealth_ctx.__enter__()
        self._pw = pw
        launch_args = ["--auto-open-devtools-for-tabs"] if self.devtools else []
        self._browser = pw.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=launch_args,
        )
        browser = self._browser
        if browser is None:
            raise RuntimeError("Browser failed to start.")
        self._context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        if self.trace_path is not None:
            self._context.tracing.start(snapshots=True, screenshots=True, sources=True)
            self._tracing_started = True
        return self

    def close(self) -> None:
        """Stop tracing, close the browser, and release Playwright resources."""
        trace_error: Exception | None = None
        if self._context is not None:
            try:
                if self._tracing_started:
                    if self.trace_path is None:
                        raise RuntimeError("Tracing started without a trace output path.")
                    self.trace_path.parent.mkdir(parents=True, exist_ok=True)
                    self._context.tracing.stop(path=str(self.trace_path))
                    self._tracing_started = False
            except Exception as error:
                trace_error = error
            finally:
                self._context.close()
                self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._stealth_ctx.__exit__(None, None, None)
            self._pw = None
        if trace_error is not None:
            raise trace_error

    def _open(self, url: str) -> Page:
        self.start()
        if self._context is None:
            raise RuntimeError("Browser session failed to start.")
        page = self._context.new_page()
        page.set_extra_http_headers({"Referer": "https://www.google.com/"})
        page.goto(url, wait_until="load")
        if self.pause_on_open:
            page.pause()
        return page
