"""Provider-neutral, permission-ready web browser foundations."""

from app.tools.advanced_browser.actions import BrowserActionService
from app.tools.advanced_browser.base import BrowserController, BrowserSession
from app.tools.advanced_browser.errors import (
    BrowserDependencyError,
    BrowserElementError,
    BrowserError,
    BrowserLimitError,
    BrowserNavigationError,
    BrowserSessionError,
    BrowserTimeoutError,
    BrowserValidationError,
)
from app.tools.advanced_browser.models import (
    UNTRUSTED_BROWSER_CONTENT_NOTICE,
    BrowserElement,
    BrowserLimits,
    BrowserTab,
    DownloadMetadata,
    FindMatch,
    PageSnapshot,
)
from app.tools.advanced_browser.playwright import PlaywrightBrowserController, PlaywrightBrowserSession
from app.tools.advanced_browser.proxy import AuthenticatedLoopbackProxy
from app.tools.advanced_browser.validation import (
    AddressResolver,
    PublicHostPolicy,
    validate_redirect_url,
    validate_web_url,
)

__all__ = [
    "UNTRUSTED_BROWSER_CONTENT_NOTICE",
    "AddressResolver",
    "AuthenticatedLoopbackProxy",
    "BrowserController",
    "BrowserActionService",
    "BrowserDependencyError",
    "BrowserElement",
    "BrowserElementError",
    "BrowserError",
    "BrowserLimitError",
    "BrowserLimits",
    "BrowserNavigationError",
    "BrowserSession",
    "BrowserSessionError",
    "BrowserTab",
    "BrowserTimeoutError",
    "BrowserValidationError",
    "DownloadMetadata",
    "FindMatch",
    "PageSnapshot",
    "PlaywrightBrowserController",
    "PlaywrightBrowserSession",
    "PublicHostPolicy",
    "validate_redirect_url",
    "validate_web_url",
]
