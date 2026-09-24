"""Import the plugin's main.py in tests without a real AstrBot runtime.

main.py imports astrbot and uses relative package imports, so loading it needs
a stub astrbot package plus a synthetic parent package. Everything here is
deliberately minimal: the point is to execute main.py, not to emulate AstrBot.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "astrbot_plugin_bilibili_media_parser"


class _EventFilter:
    class EventMessageType:
        ALL = "ALL"
        AT_MESSAGE_ONLY = "AT_MESSAGE_ONLY"
        GROUP_AT = "GROUP_AT"

    @staticmethod
    def event_message_type(*_args: Any, **_kwargs: Any):
        def decorator(func):
            return func

        return decorator

    @staticmethod
    def command_group(*_args: Any, **_kwargs: Any):
        def decorator(func):
            return func

        return decorator


class Plain:
    def __init__(self, text: str = "") -> None:
        self.type = "plain"
        self.text = text
        self.data = {"text": text}

    def __repr__(self) -> str:
        return f"Plain({self.text!r})"


class _Image:
    @staticmethod
    def fromFileSystem(path: str) -> dict[str, Any]:
        return {"type": "image", "data": {"file": str(path)}}


class _Video:
    @staticmethod
    def fromBase64(content: str) -> dict[str, Any]:
        return {"type": "video", "data": {"base64": content}}


class _Record:
    @staticmethod
    def fromBase64(content: str) -> dict[str, Any]:
        return {"type": "record", "data": {"base64": content}}


class MessageChain(list):
    def __init__(self, chain: Any = None) -> None:
        super().__init__(chain or [])


class AstrBotConfig(dict):
    """Real AstrBotConfig is a dict subclass with .get defaults."""


class Star:
    def __init__(self, context: Any = None) -> None:
        self.context = context

    async def html_render(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("tests must override html_render")


class StarTools:
    @staticmethod
    def get_data_dir(plugin_name: str = ".") -> Path:
        return Path(tempfile.mkdtemp(prefix="astrbot_stub_data_")) / plugin_name


class Context:
    """Placeholder; tests pass their own fake context."""


class AstrMessageEvent:
    pass


def install_astrbot_stub() -> None:
    """Register fake astrbot modules so importing main.py never hits the real one."""
    if getattr(install_astrbot_stub, "_installed", False):
        return

    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = logging.getLogger("astrbot-stub")
    api.AstrBotConfig = AstrBotConfig
    api.__path__ = [str(Path(tempfile.gettempdir()))]

    event_mod = types.ModuleType("astrbot.api.event")
    event_mod.AstrMessageEvent = AstrMessageEvent
    event_mod.MessageChain = MessageChain
    event_mod.filter = _EventFilter

    star_mod = types.ModuleType("astrbot.api.star")
    star_mod.Context = Context
    star_mod.Star = Star
    star_mod.StarTools = StarTools

    components = types.ModuleType("astrbot.api.message_components")
    components.Plain = Plain
    components.Image = _Image
    components.Video = _Video
    components.Record = _Record

    astrbot.api = api
    api.event = event_mod
    api.star = star_mod
    api.message_components = components

    for name, module in (
        ("astrbot", astrbot),
        ("astrbot.api", api),
        ("astrbot.api.event", event_mod),
        ("astrbot.api.star", star_mod),
        ("astrbot.api.message_components", components),
    ):
        sys.modules[name] = module

    install_astrbot_stub._installed = True


def load_plugin_main():
    """Import <project root>/main.py as a submodule of a synthetic package."""
    install_astrbot_stub()
    qualified = f"{PACKAGE_NAME}.main"
    cached = sys.modules.get(qualified)
    if cached is not None:
        return cached

    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(PROJECT_ROOT)]
    sys.modules.setdefault(PACKAGE_NAME, package)

    spec = importlib.util.spec_from_file_location(
        qualified, PROJECT_ROOT / "main.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {PROJECT_ROOT / 'main.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module
