from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentConfig:
    auth_key: str = "your_auth_key_here"
    auth_secret: str = "your_auth_secret_here"
    base_url: str = "https://uat.agentspro.cn"
    agent_id: str = "your_agent_id_here"


DEFAULT_CONFIG_FILENAME = "agent_config.local.json"
_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$")
_STRIP_CALL_RE = re.compile(r"^([\"'])(.*)\1\.strip\(\)\s*$")
_QUOTED_RE = re.compile(r"^([\"'])(.*)\1\s*$")


def _parse_assignment_style(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _ASSIGN_RE.match(line)
        if not match:
            continue

        key, expr = match.group(1), match.group(2).strip()

        strip_match = _STRIP_CALL_RE.match(expr)
        if strip_match:
            parsed[key] = strip_match.group(2).strip()
            continue

        quoted_match = _QUOTED_RE.match(expr)
        if quoted_match:
            parsed[key] = quoted_match.group(2)
            continue

        parsed[key] = expr

    return parsed


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return _parse_assignment_style(text)


def load_agent_config() -> AgentConfig:
    """Load agent config from local file + env vars.

    Priority: environment variables override local config file values.
    Supports JSON object and assignment-style file content.
    Supports uppercase and lowercase key aliases.
    """

    backend_dir = Path(__file__).resolve().parent
    config_path = Path(os.getenv("AGENT_CONFIG_PATH", str(backend_dir / DEFAULT_CONFIG_FILENAME)))
    file_cfg = _read_config(config_path)

    auth_key = os.getenv("AUTH_KEY", str(file_cfg.get("AUTH_KEY", file_cfg.get("auth_key", "")))).strip()
    auth_secret = os.getenv("AUTH_SECRET", str(file_cfg.get("AUTH_SECRET", file_cfg.get("auth_secret", "")))).strip()
    base_url = os.getenv(
        "AGENT_BASE_URL",
        str(
            file_cfg.get(
                "AGENT_BASE_URL",
                file_cfg.get("BASE_URL", file_cfg.get("base_url", "https://uat.agentspro.cn")),
            )
        ),
    ).strip()
    agent_id = os.getenv("AGENT_ID", str(file_cfg.get("AGENT_ID", file_cfg.get("agent_id", "")))).strip()

    return AgentConfig(
        auth_key=auth_key,
        auth_secret=auth_secret,
        base_url=base_url,
        agent_id=agent_id,
    )
