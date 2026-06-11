"""`/비틱` 명령 계층 단위테스트 (Discord/DB mock).

select 인터랙션·공개 발송은 라이브 확인 대상(작업지시서 테스트 전략) — 여기선
순수 헬퍼(목록 라벨·제외 안내·아이콘 매칭·득템 문구)와 본인 대상 해석 분기만 검증.
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.bitik.commands import (
    PICKUP_PHRASES,
    _self_target,
    _signed_eok,
    excluded_note,
    find_icon_url,
    pickup_text,
    potential_label,
    starforce_label,
)
from maple_mate.bitik.service import ExcludedItems, PotentialBitik, StarforceBitik


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


# ── 목록 라벨 (Q3 라벨에 손익 표기) ─────────────────────────────────────────


def test_signed_eok_signs() -> None:
    assert _signed_eok(320_000_000) == "+3억 2000만"
    assert _signed_eok(-1_489_850_040) == "-14억 8985만"
    assert _signed_eok(0) == "±0"


def test_starforce_label_format() -> None:
    label = starforce_label(_starforce())
    assert label == "여명의 가디언 엔젤 링 ★12→19 · +3억 2000만"


def test_starforce_label_fits_discord_limit() -> None:
    label = starforce_label(_starforce(item="아" * 120))
    assert len(label) <= 100


def test_potential_label_format() -> None:
    bitik = PotentialBitik(
        item="제네시스 스태프",
        item_level=200,
        reset_count=136,
        cube_counts=(),
        meso_reset_count=0,
        reset_meso=0,
        appraisal_meso=0,
        sections=(),
    )
    assert potential_label(bitik) == "제네시스 스태프 · 재설정 ×136"


# ── 제외 안내 (Q10 + 슈페리얼 파생) ─────────────────────────────────────────


def test_excluded_note_merges_unmatched_and_superior() -> None:
    excluded = ExcludedItems(unmatched=("정체불명",), superior=("타일런트 부츠",))
    assert excluded_note(excluded) == "레벨 미상 2개 제외"


def test_excluded_note_none_when_empty() -> None:
    assert excluded_note(ExcludedItems(unmatched=(), superior=())) is None


# ── 아이콘 매칭 (Q5: item-equipment 프리셋 1~3 포함 best-effort) ────────────


def _equipment_data() -> dict:
    return {
        "item_equipment": [
            {"item_name": "하이네스 워리어헬름", "item_icon": "https://icon/helm"},
        ],
        "item_equipment_preset_1": [],
        "item_equipment_preset_2": [
            {"item_name": "여명의 가디언 엔젤 링", "item_icon": "https://icon/ring"},
        ],
        "item_equipment_preset_3": None,  # null 정규화 방어
    }


def test_find_icon_url_in_current_equipment() -> None:
    assert (
        find_icon_url(_equipment_data(), "하이네스 워리어헬름") == "https://icon/helm"
    )


def test_find_icon_url_in_preset() -> None:
    assert (
        find_icon_url(_equipment_data(), "여명의 가디언 엔젤 링") == "https://icon/ring"
    )


def test_find_icon_url_miss_returns_none() -> None:
    assert find_icon_url(_equipment_data(), "거대한 공포") is None


# ── 득템 문구 (Q9: 랜덤 풀 + 선택적 코멘트) ─────────────────────────────────


def test_pickup_text_uses_comment_when_given() -> None:
    assert pickup_text("내가 더 잘 씀") == "내가 더 잘 씀"


def test_pickup_text_random_from_pool() -> None:
    assert pickup_text(None) in PICKUP_PHRASES
    assert pickup_text("  ") in PICKUP_PHRASES  # 공백만 입력 → 풀 사용


# ── 본인 대상 해석 (Q1: 본인만, 미등록/키 미등록 ephemeral 안내) ─────────────


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        rows = self._rows
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


def _registration(api_key: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=1,
        discord_user_id=2,
        maple_nickname="손바",
        ocid="oc1",
        api_key_encrypted=api_key,
    )


async def test_self_target_unregistered() -> None:
    target, error = await _self_target(lambda: _FakeSession([]), 1, 2)
    assert target is None
    assert error is not None and "/등록" in error


async def test_self_target_without_key() -> None:
    target, error = await _self_target(
        lambda: _FakeSession([_registration(None)]), 1, 2
    )
    assert target is None
    assert error is not None and "개인 키" in error


async def test_self_target_success() -> None:
    target, error = await _self_target(
        lambda: _FakeSession([_registration("enc")]), 1, 2
    )
    assert error is None
    assert target is not None and target.nickname == "손바"
