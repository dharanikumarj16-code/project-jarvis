"""Permission-ready browser service and explicit JARVIS action registration."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from urllib.parse import urlencode, urlsplit

from app.tools.advanced_browser.base import BrowserController, BrowserSession
from app.tools.advanced_browser.errors import BrowserElementError, BrowserError, BrowserSessionError
from app.tools.advanced_browser.models import BrowserElement, PageSnapshot
from app.events import event_bus


class BrowserActionService:
    """Maintain one explicit active browser session and snapshot target state.

    Element actions require the caller to repeat the role and accessible name
    observed in the latest snapshot. This keeps the permission prompt meaningful
    and prevents an opaque element identifier from being approved in isolation.
    """

    def __init__(self, controller: BrowserController) -> None:
        if not isinstance(controller, BrowserController):
            raise TypeError("controller must implement BrowserController")
        self.controller = controller
        self.events = event_bus
        self._active: BrowserSession | None = None
        self._snapshot: PageSnapshot | None = None
        self._lock = asyncio.Lock()

    @property
    def active_session_id(self) -> str | None:
        return None if self._active is None else self._active.session_id

    async def start(self) -> BrowserSession:
        async with self._lock:
            if self._active is not None:
                return self._active
            self._active = await self.controller.create_session()
            self._snapshot = None
        await self._emit("BrowserStarted", {"session_id": self._active.session_id})
        return self._active

    async def close(self) -> None:
        """Close the active session while keeping the controller reusable."""

        async with self._lock:
            session = self._active
            self._active = None
            self._snapshot = None
        if session is not None:
            await self.controller.close_session(session.session_id)

    async def shutdown(self) -> None:
        """Close every browser resource owned by the controller."""

        async with self._lock:
            self._active = None
            self._snapshot = None
        await self.controller.close()

    async def session(self) -> BrowserSession:
        if self._active is None:
            await self.start()
        return self._active

    async def navigate(self, url: str) -> str:
        sess = await self.session()
        destination = await sess.navigate(url)
        self._snapshot = None
        await self._emit(
            "BrowserNavigationCompleted",
            {
                "session_id": sess.session_id,
                "origin": _origin(destination),
                "path_character_count": len(urlsplit(destination).path),
                "has_query": bool(urlsplit(destination).query),
            },
        )
        return destination

    async def snapshot(self) -> PageSnapshot:
        sess = await self.session()
        self._snapshot = await sess.snapshot()
        return self._snapshot

    def target(self, element_id: str, expected_role: str, expected_name: str) -> BrowserElement:
        if self._snapshot is None:
            raise BrowserElementError("Take a fresh browser snapshot before interacting")
        element = next(
            (item for item in self._snapshot.elements if item.element_id == element_id),
            None,
        )
        if element is None:
            raise BrowserElementError("The element is not present in the latest snapshot")
        if element.role != expected_role or element.name != expected_name:
            raise BrowserElementError("The element role or accessible name changed")
        if element.disabled:
            raise BrowserElementError("The requested browser element is disabled")
        return element

    async def click(self, element_id: str, expected_role: str, expected_name: str) -> None:
        self.target(element_id, expected_role, expected_name)
        sess = await self.session()
        await sess.click(element_id)
        self._snapshot = None

    async def type_text(
        self,
        element_id: str,
        expected_role: str,
        expected_name: str,
        text: str,
        *,
        clear: bool,
    ) -> None:
        self.target(element_id, expected_role, expected_name)
        sess = await self.session()
        await sess.type_text(element_id, text, clear=clear)
        self._snapshot = None

    async def press_key(
        self,
        element_id: str,
        expected_role: str,
        expected_name: str,
        key: str,
    ) -> None:
        self.target(element_id, expected_role, expected_name)
        sess = await self.session()
        await sess.press_key(element_id, key)
        self._snapshot = None

    async def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self.events is not None:
            await self.events.publish(name, payload)


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"
