from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from classcorpus.models import SlideRecord

ParseFunction = Callable[[Path, Path], list[SlideRecord]]


@dataclass(frozen=True, slots=True)
class ParserPlugin:
    name: str
    suffixes: tuple[str, ...]
    parse: ParseFunction


class ParserRegistry:
    def __init__(self):
        self._by_suffix: dict[str, ParserPlugin] = {}

    def register(self, plugin: ParserPlugin) -> None:
        if not plugin.name.strip():
            raise ValueError("parser plugin name must not be blank")
        if not plugin.suffixes:
            raise ValueError("parser plugin must declare at least one suffix")
        normalized: list[str] = []
        for suffix in plugin.suffixes:
            value = suffix.casefold()
            if not value.startswith(".") or len(value) == 1:
                raise ValueError("parser suffixes must start with a dot")
            if value in normalized:
                raise ValueError(f"duplicate suffix in parser plugin: {value}")
            if value in self._by_suffix:
                owner = self._by_suffix[value].name
                raise ValueError(
                    f"parser suffix {value} is already registered by {owner}"
                )
            normalized.append(value)
        for suffix in normalized:
            self._by_suffix[suffix] = plugin

    def parser_for(self, suffix: str) -> ParserPlugin | None:
        return self._by_suffix.get(suffix.casefold())

    def supported_suffixes(self) -> frozenset[str]:
        return frozenset(self._by_suffix)


__all__ = ["ParserPlugin", "ParserRegistry"]

