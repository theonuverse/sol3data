"""Shared character-page navigation and asynchronous panel loading helpers."""
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

_ACTIVE_PANEL_SELECTOR = ".tab-inside.active:visible"


def active_panel(page: Page) -> Locator:
    """Return the visible character tab panel."""
    panel = page.locator(_ACTIVE_PANEL_SELECTOR)
    panel.first.wait_for(state="visible")
    return panel.first


def wait_for_panel_content(panel: Locator, *, timeout: float = 30_000) -> Locator:
    """Wait until an asynchronously loaded panel is no longer showing Loading."""
    loading = panel.get_by_text("Loading...", exact=True)
    if loading.count():
        loading.first.wait_for(state="hidden", timeout=timeout)
    try:
        panel.locator("h5, h6, table, .section-analysis, li, img[alt]").first.wait_for(
            state="visible",
            timeout=timeout,
        )
    except PlaywrightTimeoutError:
        # Some optional panels legitimately contain plain text only. Returning
        # the visible panel preserves the section-specific empty-data behavior.
        pass
    return panel
