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
    env = {
        k: v for k, v in _VALID.items() if k not in ("NEXON_APP_KEY", "DATABASE_URL")
    }
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


def test_dev_guild_id_absent_is_none():
    # 운영 배포: DEV_GUILD_ID 미설정 → 기동 성공 + None(글로벌 동기화).
    env = {k: v for k, v in _VALID.items() if k != "DEV_GUILD_ID"}
    cfg = Config.from_env(env)
    assert cfg.dev_guild_id is None


def test_dev_guild_id_empty_is_none():
    cfg = Config.from_env({**_VALID, "DEV_GUILD_ID": "   "})
    assert cfg.dev_guild_id is None


def test_dev_guild_id_invalid_still_errors():
    # 값이 있으면 정수여야 함 — 잘못된 값은 여전히 형식오류.
    with pytest.raises(ConfigError) as exc:
        Config.from_env({**_VALID, "DEV_GUILD_ID": "not-int"})
    assert "DEV_GUILD_ID" in exc.value.invalid


# ── NEXON_THROTTLE (스케일 튜닝 3-1, ADR-0004) ───────────────────────


def test_nexon_throttle_absent_uses_default():
    cfg = Config.from_env(_VALID)
    assert cfg.nexon_throttle == 0.25


def test_nexon_throttle_parsed_as_float():
    cfg = Config.from_env({**_VALID, "NEXON_THROTTLE": "0.02"})
    assert cfg.nexon_throttle == 0.02


def test_nexon_throttle_empty_is_default():
    cfg = Config.from_env({**_VALID, "NEXON_THROTTLE": "  "})
    assert cfg.nexon_throttle == 0.25


def test_nexon_throttle_invalid_errors():
    with pytest.raises(ConfigError) as exc:
        Config.from_env({**_VALID, "NEXON_THROTTLE": "fast"})
    assert "NEXON_THROTTLE" in exc.value.invalid


async def test_build_deps_injects_nexon_throttle():
    # 조립부(main.build_deps)가 NEXON_THROTTLE 을 NexonClient 앱 키 버킷 간격으로 주입.
    from cryptography.fernet import Fernet

    from maple_mate.main import build_deps

    cfg = Config.from_env(
        {
            **_VALID,
            "FERNET_MASTER_KEY": Fernet.generate_key().decode(),
            "NEXON_THROTTLE": "0.07",
        }
    )
    deps, engine = build_deps(cfg)
    try:
        assert deps.nexon._throttle == 0.07
    finally:
        await deps.nexon.aclose()
        await engine.dispose()
