"""환경변수(.env) fail-fast 로딩 (빌드 단위 #2).

필수 키가 비어 있거나 형식이 잘못되면 기동을 거부한다. 누락/형식오류 항목을 한 번에 모아서
명확한 메시지로 보고한다. `Config.from_env` 은 순수 함수라 .env 없이 단위테스트 가능.
필수 키 목록은 docs/phase1-handoff.md §4 표 기준.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# 비어 있으면 안 되는 문자열 키
_REQUIRED_STR_KEYS = (
    "DISCORD_BOT_TOKEN",
    "NEXON_APP_KEY",
    "FERNET_MASTER_KEY",
    "OPERATOR_TOKEN",
    "DATABASE_URL",
)
# 정수(Discord snowflake)로 파싱돼야 하는 키
_REQUIRED_INT_KEYS = (
    "ADMIN_CHANNEL_ID",
    "DEV_GUILD_ID",
)


class ConfigError(RuntimeError):
    """필수 환경변수 누락/형식오류. 기동 거부 신호."""

    def __init__(self, missing: list[str], invalid: list[str]):
        self.missing = list(missing)
        self.invalid = list(invalid)
        parts: list[str] = []
        if self.missing:
            parts.append("누락된 필수 환경변수: " + ", ".join(self.missing))
        if self.invalid:
            parts.append("형식이 잘못된 환경변수(정수 필요): " + ", ".join(self.invalid))
        super().__init__(" / ".join(parts) or "환경설정 오류")


@dataclass(frozen=True)
class Config:
    discord_bot_token: str
    nexon_app_key: str
    fernet_master_key: str
    operator_token: str
    database_url: str
    admin_channel_id: int
    dev_guild_id: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        """매핑(os.environ 등)에서 Config 생성. 누락/형식오류 시 ConfigError."""
        missing: list[str] = []
        invalid: list[str] = []
        strs: dict[str, str] = {}
        ints: dict[str, int] = {}

        for key in _REQUIRED_STR_KEYS:
            value = (env.get(key) or "").strip()
            if not value:
                missing.append(key)
            else:
                strs[key] = value

        for key in _REQUIRED_INT_KEYS:
            raw = (env.get(key) or "").strip()
            if not raw:
                missing.append(key)
                continue
            try:
                ints[key] = int(raw)
            except ValueError:
                invalid.append(key)

        if missing or invalid:
            raise ConfigError(missing, invalid)

        return cls(
            discord_bot_token=strs["DISCORD_BOT_TOKEN"],
            nexon_app_key=strs["NEXON_APP_KEY"],
            fernet_master_key=strs["FERNET_MASTER_KEY"],
            operator_token=strs["OPERATOR_TOKEN"],
            database_url=strs["DATABASE_URL"],
            admin_channel_id=ints["ADMIN_CHANNEL_ID"],
            dev_guild_id=ints["DEV_GUILD_ID"],
        )


def load_config(dotenv_path: str | None = None) -> Config:
    """.env 를 os.environ 으로 로드한 뒤 Config 생성. 기동 진입점에서 사용."""
    from dotenv import load_dotenv

    load_dotenv(dotenv_path)  # 이미 설정된 os.environ 값은 보존(override=False 기본)
    return Config.from_env(os.environ)
