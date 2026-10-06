"""Public exception types for the scraper API."""


class Sol3DataError(Exception):
    """Base class for errors raised by sol3data."""


class SectionUnavailableError(Sol3DataError):
    """A requested page section is not available."""


class CollectionItemNotFoundError(Sol3DataError, ValueError):
    """A named or numbered collection item does not exist."""


class NavigationError(Sol3DataError):
    """A page could not be opened or navigated."""


class PageStructureChangedError(Sol3DataError):
    """The source page no longer matches the supported structure."""
