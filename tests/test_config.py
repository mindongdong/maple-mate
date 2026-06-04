"""config.py fail-fast 단위테스트 (handoff §6: .env 누락 시 예외)."""
from __future__ import annotations

import pytest

from maple_mate.config import Config, ConfigError

_VALID = {
    "DISCORD_BOT_TOKEN": "token",
    "NEXON_APP_KEY": "appkey",
    "FERNET_MASTER_KEY": "masterkey",
    "OPERATOR_TOKEN": "optoken",
    "DATABASE_URL": "postgresql+asyncpg://u@localhost/db",
    "ADMIN_CHANNEL_ID": "123",
    "DEV_GUILD_ID": "456",
}


def test_valid_env_builds_config():
    cfg = Config.from_env(_VALID)
    assert cfg.discord_bot_token == "token"
    assert cfg.admin_channel_id == 123
    assert cfg.dev_guild_id == 456


def test_missing_keys_raise_with_names():
    env = {k: v for k, v in _VALID.items() if k not in ("NEXON_APP_KEY", "DATABASE_URL")}
    with pytest.raises(ConfigError) as exc:
        Config.from_env(env)
    assert set(exc.value.missing) == {"NEXON_APP_KEY", "DATABASE_URL"}


def test_empty_string_counts_as_missing():
    env = {**_VALID, "DISCORD_BOT_TOKEN": "   "}
    with pytest.raises(ConfigError) as exc:
        Config.from_env(env)
    assert "DISCORD_BOT_TOKEN" in exc.value.missing


def test_non_integer_id_is_invalid():
    env = {**_VALID, "ADMIN_CHANNEL_ID": "not-a-number"}
    with pytest.raises(ConfigError) as exc:
        Config.from_env(env)
    assert "ADMIN_CHANNEL_ID" in exc.value.invalid


def test_config_is_frozen():
    cfg = Config.from_env(_VALID)
    with pytest.raises(Exception):
        cfg.discord_bot_token = "x"  # type: ignore[misc]
