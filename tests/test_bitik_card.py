"""`/비틱` 자랑 카드 PNG 렌더 스모크 테스트 (예외 없이 PNG 생성 + 아이콘 None 분기)."""

from __future__ import annotations

import io

from PIL import Image

from maple_mate.bitik.service import PotentialBitik, PotentialSection, StarforceBitik
from maple_mate.bot import bitik_card

_PERIOD = "2025-06-07 ~ 2026-06-07"


def _starforce(**kw) -> StarforceBitik:
    base = dict(
        item="여명의 가디언 엔젤 링",
        level=160,
        start_star=12,
        end_star=19,
        attempt_count=19,
        destroy_count=0,
        actual_meso=1_023_400_320,
        expected_meso=1_343_400_320,
        net_meso=320_000_000,
        challenge_star=19,
        challenge_success=1,
        challenge_fail=4,
    )
    base.update(kw)
    return StarforceBitik(**base)


def _potential(**kw) -> PotentialBitik:
    base = dict(
        item="제네시스 스태프",
        item_level=200,
        reset_count=111,
        cube_counts=(("레드 큐브", 65), ("블랙 큐브", 23), ("수상한 큐브", 20)),
        meso_reset_count=3,
        reset_meso=7_770_400_000,
        appraisal_meso=88_800_000,
        sections=(
            PotentialSection(
                kind="잠재능력",
                start_grade="유니크",
                end_grade="레전드리",
                end_options=("보공 +40%", "공격력 +12%", "공격력 +9%"),
            ),
            PotentialSection(
                kind="에디셔널 잠재능력",
                start_grade="레어",
                end_grade="에픽",
                end_options=("STR +6%",),
            ),
        ),
    )
    base.update(kw)
    return PotentialBitik(**base)


def _fake_icon() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (32, 32), (255, 156, 56, 255)).save(buf, "PNG")
    return buf.getvalue()


def _is_png(data: bytes) -> bool:
    img = Image.open(io.BytesIO(data))
    img.verify()
    return img.format == "PNG"


def test_starforce_card_with_icon() -> None:
    assert _is_png(
        bitik_card.render_starforce_card(_starforce(), _fake_icon(), _PERIOD)
    )


def test_starforce_card_without_icon() -> None:
    assert _is_png(bitik_card.render_starforce_card(_starforce(), None, _PERIOD))


def test_starforce_card_loss_variant() -> None:
    """손해(net 음수)·파괴 포함 변형도 렌더된다(색 분기 경로)."""
    loss = _starforce(
        start_star=17,
        end_star=17,
        attempt_count=4,
        destroy_count=1,
        expected_meso=0,
        net_meso=-1_489_850_040,
        actual_meso=1_489_850_040,
        challenge_star=18,
        challenge_success=0,
        challenge_fail=4,
    )
    assert _is_png(bitik_card.render_starforce_card(loss, None, _PERIOD))


def test_potential_card_with_icon() -> None:
    assert _is_png(
        bitik_card.render_potential_card(_potential(), _fake_icon(), _PERIOD)
    )


def test_potential_card_without_appraisal_or_icon() -> None:
    """감정비 0(저레벨 큐브)·아이콘 없음·단일 섹션 변형."""
    bitik = _potential(
        appraisal_meso=0,
        cube_counts=(),
        meso_reset_count=5,
        reset_count=5,
        sections=(
            PotentialSection(
                kind="잠재능력",
                start_grade="레전드리",
                end_grade="레전드리",
                end_options=("보공 +40%", "공격력 +12%", "몬스터 방어율 무시 +30%"),
            ),
        ),
    )
    assert _is_png(bitik_card.render_potential_card(bitik, None, _PERIOD))
