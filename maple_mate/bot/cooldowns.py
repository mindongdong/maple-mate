"""명령군별 per-user 쿨다운 (스케일 튜닝 3-3, D3).

discord.py 내장 `app_commands.checks.cooldown` 사용 — in-memory 라 단일 인스턴스 전제
(단계 3 분산 시 재검토). 키 = (guild_id, user.id): 같은 유저라도 서버가 다르면 독립.
`/핑` 은 쿨다운 제외. 초과 시 안내는 트리 공통 핸들러(core.on_app_command_error)가 담당.

각 팩토리는 호출마다 새 데코레이터(=독립 버킷 매핑)를 만든다 — 데코레이터 객체를
여러 명령에 재사용하면 명령 간 쿨다운이 공유되므로 반드시 명령마다 새로 만든다.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable

import discord
from discord import app_commands

# 명령군별 간격(초): 1회 / N초 (그릴링 D3).
HISTORY_PER = 30.0  # 이력류 /스타포스 /잠재 — cold 1건이 개인 키 수십~수백 콜
SPEC_PER = 10.0  # 스펙류 /스펙 /아이템 /유니온
SETTINGS_PER = 5.0  # 등록·설정류 /등록 /썬데이 /공지알림


def _per_user(interaction: discord.Interaction) -> Hashable:
    return (interaction.guild_id, interaction.user.id)


def history_cooldown() -> Callable:
    """이력류: 1회/30초 per-user."""
    return app_commands.checks.cooldown(1, HISTORY_PER, key=_per_user)


def spec_cooldown() -> Callable:
    """스펙류: 1회/10초 per-user."""
    return app_commands.checks.cooldown(1, SPEC_PER, key=_per_user)


def settings_cooldown() -> Callable:
    """등록·설정류: 1회/5초 per-user."""
    return app_commands.checks.cooldown(1, SETTINGS_PER, key=_per_user)
