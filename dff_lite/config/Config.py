# config/Config.py — YAML configuration loader
"""Loads and persists application configuration from YAML."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from dff_lite.core.Models import AppConfig

logger = logging.getLogger("dff_lite.config")

DEFAULT_CONFIG_NAME = "CONFIG/dff_lite_config.yaml"


def project_root() -> Path:
    """Return the DFF Lite project directory."""
    return Path(__file__).resolve().parent.parent.parent


def default_config_dict() -> Dict[str, Any]:
    return AppConfig().model_dump()


def save_default_config(path: Path) -> AppConfig:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = default_config_dict()
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    logger.info("Wrote default configuration to %s", path)
    return AppConfig.model_validate(data)


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Load YAML config; create default beside project root if missing.
    Merges partial YAML over pydantic defaults.
    """
    if config_path is None:
        config_path = project_root() / DEFAULT_CONFIG_NAME

    if not config_path.exists():
        logger.warning("Config not found at %s — creating defaults.", config_path)
        return save_default_config(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    base = AppConfig().model_dump()
    merged = _deep_merge(base, raw)
    return AppConfig.model_validate(merged)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
