"""
Runtime configuration helpers for the isolated dev copy.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")


def _load_simple_yaml_section(section_name: str) -> Dict[str, str]:
    config_path = _PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        return {}

    values: Dict[str, str] = {}
    current_section = ""
    for raw_line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            continue

        if current_section != section_name or not line.startswith("  "):
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value

    return values


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_go_api_base() -> str:
    return os.getenv("GO_API_BASE") or os.getenv("GO_API_URL") or "http://localhost:18080"


def get_ai_api_base() -> str:
    return os.getenv("AI_API_BASE") or f"http://localhost:{get_ai_port()}"


def get_ai_host() -> str:
    return os.getenv("AI_HOST", "0.0.0.0")


def get_ai_port() -> int:
    return _get_int("AI_PORT", 18081)


def get_redis_settings() -> Tuple[str, int, int]:
    cfg = _load_simple_yaml_section("redis")
    return (
        os.getenv("REDIS_HOST") or cfg.get("host") or "localhost",
        _get_int("REDIS_PORT", int(cfg.get("port", "6379"))),
        _get_int("REDIS_DB", int(cfg.get("db", "1"))),
    )


def get_postgres_settings() -> Tuple[str, int, str, str, str]:
    cfg = _load_simple_yaml_section("database")
    return (
        os.getenv("PG_HOST") or cfg.get("host") or "localhost",
        _get_int("PG_PORT", int(cfg.get("port", "5432"))),
        os.getenv("PG_USER") or cfg.get("user") or "postgres",
        os.getenv("PG_PASSWORD") or cfg.get("password") or "",
        os.getenv("PG_DATABASE") or cfg.get("name") or "postgres",
    )
