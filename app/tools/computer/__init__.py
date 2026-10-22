"""Safe, mockable adapters for local computer capabilities."""

from app.tools.computer._pyautogui import PyAutoGUIAdapter
from app.tools.computer.applications import (
    ApplicationController,
    ApplicationDefinition,
    ApplicationResolver,
    ResolvedApplication,
    RunningApplication,
    WindowsTrustedPathProvider,
)
from app.tools.computer.errors import (
    ApplicationControlError,
    ApplicationError,
    ApplicationLaunchError,
    ApplicationNotFoundError,
    ApplicationUnavailableError,
    AutomationUnavailableError,
    ComputerError,
    ComputerValidationError,
    ScreenshotError,
    UnsupportedPlatformError,
    WindowError,
    WindowFocusError,
    WindowNotFoundError,
)
from app.tools.computer.keyboard import KeyboardController
from app.tools.computer.mouse import MouseController, Point
from app.tools.computer.screen import (
    PillowImageGrabProvider,
    ScreenController,
    Screenshot,
    ScreenshotStore,
)
from app.tools.computer.system import SystemInfoProvider, SystemInformation
from app.tools.computer.windows import WindowBounds, WindowInformation, WindowsController

__all__ = [
    "ApplicationControlError",
    "ApplicationController",
    "ApplicationDefinition",
    "ApplicationError",
    "ApplicationLaunchError",
    "ApplicationNotFoundError",
    "ApplicationResolver",
    "ApplicationUnavailableError",
    "AutomationUnavailableError",
    "ComputerError",
    "ComputerValidationError",
    "KeyboardController",
    "MouseController",
    "PillowImageGrabProvider",
    "Point",
    "PyAutoGUIAdapter",
    "ResolvedApplication",
    "RunningApplication",
    "ScreenController",
    "Screenshot",
    "ScreenshotError",
    "ScreenshotStore",
    "SystemInfoProvider",
    "SystemInformation",
    "UnsupportedPlatformError",
    "WindowBounds",
    "WindowError",
    "WindowFocusError",
    "WindowInformation",
    "WindowNotFoundError",
    "WindowsController",
    "WindowsTrustedPathProvider",
]
