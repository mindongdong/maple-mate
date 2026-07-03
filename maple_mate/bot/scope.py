"""유저 설치 스코프 해석 — 센티널 guild_id=0 "DM 워크스페이스" (ADR-0019).

개방 명령이 공유하는 데이터 스코프 결정을 한 곳에 둔다. 길드(봇 초대됨)=기존 guild_id,
유저 설치 봇 DM=DM_WORKSPACE_ID(0), 그 외(봇 미초대 서버의 유저 설치 호출 등)=None(거부).
스키마·서비스층 무변경 — 호출부가 guild_id 자리에 scope 를 그대로 전달한다(결정 2).

데코레이터 배선(§3-2)의 그룹용 상수도 여기 모은다 — 명령은 `@app_commands.allowed_installs`
데코레이터, 프로그램 생성 그룹은 생성자 kwargs 로 지정한다(둘 다 기본값 드리프트 방지 명시).
"""

from __future__ import annotations

import discord
from discord import app_commands

DM_WORKSPACE_ID = 0  # 센티널 — Discord 스노우플레이크에 0 없음 (ADR-0019 결정 2)

# resolve_scope 가 None 을 돌려줬을 때 호출부가 내보내는 공용 거부 문구(§3-1).
MSG_UNAVAILABLE = "이 명령은 서버 채널 또는 봇 DM에서 사용할 수 있어요."

# 그룹 생성자용 배선 상수(§3-2). 개방 = 유저 설치 + 봇 DM 허용(그룹 DM 은 항상 차단).
# 미개방 = 길드 설치 전용 + 길드 컨텍스트 전용 — 명시해서 포털 기본값 드리프트를 막는다.
OPEN_INSTALLS = app_commands.AppInstallationType(guild=True, user=True)
OPEN_CONTEXTS = app_commands.AppCommandContext(
    guild=True, dm_channel=True, private_channel=False
)
GUILD_INSTALLS = app_commands.AppInstallationType(guild=True, user=False)
GUILD_CONTEXTS = app_commands.AppCommandContext(
    guild=True, dm_channel=False, private_channel=False
)


def _is_user_install(interaction: discord.Interaction) -> bool:
    """유저 설치 경로 인터랙션인가. 판별 메서드가 없는 가짜(테스트 SimpleNamespace)는 길드 설치로 간주."""
    checker = getattr(interaction, "is_user_integration", None)
    return checker is not None and checker()


def resolve_scope(interaction: discord.Interaction) -> int | None:
    """개방 명령의 데이터 스코프. None = 사용 불가 컨텍스트(호출부가 MSG_UNAVAILABLE 안내 후 종료).

    - 길드(봇 초대됨): 기존 guild_id 그대로 — 길드 경로 회귀 0.
    - 봇 미초대 서버의 유저 설치 호출: None — 공개 채널 노출·실서버 guild_id 와 센티널 키
      충돌을 막는다(ADR-0019 결정 4).
    - 봇 DM: **유저 설치 인터랙션만** DM 워크스페이스(0). 길드 설치 전용 DM(서버 공유
      유저의 봇 DM, `_integration_owners={0: 0}`)은 기존대로 거부 — 서버 등록과 별개인
      guild 0 데이터를 서버 데이터로 오인하는 혼란을 막는다(결정 1).
    - 그룹 DM 은 allowed_contexts(private_channels=False) 로 노출 자체를 막는다(결정 4).
    """
    if interaction.guild_id is not None:
        if _is_user_install(interaction) and not interaction.is_guild_integration():
            return None
        return interaction.guild_id
    return DM_WORKSPACE_ID if _is_user_install(interaction) else None
