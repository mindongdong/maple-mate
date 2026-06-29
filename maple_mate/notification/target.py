"""`대상`(채널/개인) 슬래시 파라미터 + 발송 대상 파싱 (ADR-0017 결정 2·4).

경험치·공지·썬데이의 `켜기`/`끄기`가 공유한다. `채널`=공용 채널 발송(channel_settings),
`개인`=본인 DM 구독(notification_subscription). 둘은 독립이라 한 사람이 동시에 켤 수 있다.

기본값 비대칭(결정 4): **켜기 미지정=채널만**(기존 동작 보존), **끄기 미지정=둘 다 해제**
("그만 받기"가 가장 흔한 의도). `대상:채널`/`대상:개인`으로 한쪽만 콕 집는다. 순수.
"""

from __future__ import annotations

from discord import app_commands

TARGET_CHANNEL = "channel"
TARGET_PERSONAL = "personal"

# 대상 Choice — rename 은 항상 "대상", describe 는 호출부 문구.
TARGET_CHOICES = [
    app_commands.Choice(name="채널", value=TARGET_CHANNEL),
    app_commands.Choice(name="개인", value=TARGET_PERSONAL),
]
TARGET_DESCRIBE = "받을 곳 (채널=공용 채널 발송 / 개인=본인 DM)"


def targets_for(
    choice: app_commands.Choice[str] | None, *, enabling: bool
) -> tuple[bool, bool]:
    """대상 choice → (채널 적용?, 개인 적용?). 미지정 기본값 비대칭(결정 4). 순수.

    `대상:채널`=(True, False), `대상:개인`=(False, True). 미지정은 켜기=(True, False),
    끄기=(True, True)(둘 다 해제).
    """
    if choice is not None:
        return choice.value == TARGET_CHANNEL, choice.value == TARGET_PERSONAL
    return (True, False) if enabling else (True, True)
