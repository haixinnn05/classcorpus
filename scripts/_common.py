from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def emit(payload: dict[str, Any], *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def fail(error: Exception, *, json_mode: bool) -> int:
    emit(
        {
            "ok": False,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        },
        json_mode=json_mode,
    )
    return 1


class AgentArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--json" in sys.argv[1:]:
            emit(
                {
                    "ok": False,
                    "error": {
                        "type": "ArgumentError",
                        "message": message,
                    },
                },
                json_mode=True,
            )
            raise SystemExit(1)
        super().error(message)


def argument_parser(*, description: str) -> AgentArgumentParser:
    return AgentArgumentParser(description=description)
