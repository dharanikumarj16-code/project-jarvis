"""Validated mouse-control abstraction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.tools.computer._pyautogui import PyAutoGUIAdapter
from app.tools.computer.errors import ComputerValidationError

MAX_SCROLL_CLICKS = 10_000
MAX_MOVE_DURATION = 30.0
VALID_BUTTONS = frozenset({"left", "middle", "right"})


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


class MouseBackend(Protocol):
    """Mockable boundary implemented by :class:`PyAutoGUIAdapter`."""

    def size(self) -> tuple[int, int]: ...

    def position(self) -> tuple[int, int]: ...

    def move_to(self, x: int, y: int, *, duration: float) -> None: ...

    def click(self, *, x: int | None, y: int | None, button: str) -> None: ...

    def double_click(self, *, x: int | None, y: int | None, button: str) -> None: ...

    def scroll(self, clicks: int) -> None: ...

    def scroll(self, clicks: int) -> None: ...

    def drag_to(self, x: int, y: int, *, duration: float, button: str) -> None: ...


class MouseController:
    """Validate every mouse request before invoking the real backend."""

    def __init__(self, backend: MouseBackend | None = None) -> None:
        self._backend = backend or PyAutoGUIAdapter()

    def position(self) -> Point:
        x, y = self._backend.position()
        return Point(int(x), int(y))

    def center(self) -> Point:
        width, height = self._backend.size()
        return Point(width // 2, height // 2)

    def move(self, x: int, y: int, *, duration: float = 0.2) -> Point:
        point = self._validate_point(x, y)
        duration = _validate_duration(duration)
        self._backend.move_to(point.x, point.y, duration=duration)
        return point

    def click(
        self,
        x: int | None = None,
        y: int | None = None,
        *,
        button: str = "left",
    ) -> None:
        point = self._validate_optional_point(x, y)
        button = _validate_button(button)
        self._backend.click(
            x=point.x if point else None,
            y=point.y if point else None,
            button=button,
        )

    def double_click(
        self,
        x: int | None = None,
        y: int | None = None,
        *,
        button: str = "left",
    ) -> None:
        point = self._validate_optional_point(x, y)
        button = _validate_button(button)
        self._backend.double_click(
            x=point.x if point else None,
            y=point.y if point else None,
            button=button,
        )

    def right_click(self, x: int | None = None, y: int | None = None) -> None:
        self.click(x, y, button="right")

    def drag(
        self,
        x: int,
        y: int,
        *,
        duration: float = 0.5,
        button: str = "left",
    ) -> Point:
        point = self._validate_point(x, y)
        duration = _validate_duration(duration)
        button = _validate_button(button)
        self._backend.drag_to(point.x, point.y, duration=duration, button=button)
        return point

    def scroll(self, clicks: int) -> None:
        if isinstance(clicks, bool) or not isinstance(clicks, int):
            raise ComputerValidationError("scroll clicks must be an integer")
        if clicks == 0 or abs(clicks) > MAX_SCROLL_CLICKS:
            raise ComputerValidationError(
                f"scroll clicks must be between {-MAX_SCROLL_CLICKS} and "
                f"{MAX_SCROLL_CLICKS}, excluding zero"
            )
        self._backend.scroll(clicks)

    def hscroll(self, clicks: int) -> None:
        if isinstance(clicks, bool) or not isinstance(clicks, int):
            raise ComputerValidationError("scroll clicks must be an integer")
        if clicks == 0 or abs(clicks) > MAX_SCROLL_CLICKS:
            raise ComputerValidationError(
                f"scroll clicks must be between {-MAX_SCROLL_CLICKS} and "
                f"{MAX_SCROLL_CLICKS}, excluding zero"
            )
        self._backend.hscroll(clicks)

    def _validate_optional_point(self, x: int | None, y: int | None) -> Point | None:
        if x is None and y is None:
            return None
        if x is None or y is None:
            raise ComputerValidationError("x and y coordinates must be supplied together")
        return self._validate_point(x, y)

    def _validate_point(self, x: int | float | str, y: int | float | str) -> Point:
        try:
            if isinstance(x, bool) or isinstance(y, bool):
                raise ValueError
            nx = int(round(float(x)))
            ny = int(round(float(y)))
        except (ValueError, TypeError):
            raise ComputerValidationError("coordinates must be integers")
        width, height = self._backend.size()
        if width <= 0 or height <= 0:
            raise ComputerValidationError("desktop dimensions are unavailable")
        if not (0 <= nx < width and 0 <= ny < height):
            raise ComputerValidationError(
                f"coordinates must be within the desktop bounds 0..{width - 1}, 0..{height - 1}"
            )
        return Point(nx, ny)


def _validate_duration(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComputerValidationError("duration must be a number")
    duration = float(value)
    if not math.isfinite(duration) or not 0 <= duration <= MAX_MOVE_DURATION:
        raise ComputerValidationError(
            f"duration must be between 0 and {MAX_MOVE_DURATION:g} seconds"
        )
    return duration


def _validate_button(value: str) -> str:
    if not isinstance(value, str):
        raise ComputerValidationError("mouse button must be text")
    button = value.casefold().strip()
    if button not in VALID_BUTTONS:
        raise ComputerValidationError(f"mouse button must be one of {sorted(VALID_BUTTONS)}")
    return button
