"""데모 스크린샷 생성 — 봇의 실제 렌더러를 가짜 닉 픽스처로 호출해 진짜 PNG 를 만든다.

디스코드 메시지 캡처가 아니라 "그 기능이 만드는 이미지 출력물" 그 자체다. 실 유저
데이터는 없고(가짜 닉), 결과 PNG 는 site/public/shots/ 에 커밋해 사이트가 <img> 로
서빙한다(Vercel 빌드에 파이썬 불필요). 봇 렌더 코드가 바뀌면 이 스크립트를 재실행해
재커밋하면 사이트와 실제 출력의 드리프트가 0 이다.

실행(레포 루트):
    .venv/bin/python site/scripts/render_demo_shots.py

데모 캐스트(전 샷 일관, Embeds.tsx 값 계승): 홍길동전사 · 불꽃아크 · 바람궁수
(+ 경험치 그래프는 이글루법사 · 캐논슈터 추가).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))  # 레포 루트 기준 실행 — maple_mate 패키지 import

from maple_mate.bot.item_card import (  # noqa: E402
    CardPotential,
    ItemCard,
    render_item_cards,
)
from maple_mate.bot.leaderboard_image import render_progress_graph  # noqa: E402
from maple_mate.bot.table_image import (  # noqa: E402
    GradeBadges,
    Highlight,
    NumGrid,
    render_table_image,
)

_OUT = _ROOT / "site" / "public" / "shots"
_ICONS = Path(__file__).resolve().parent / "icons"


def _icon(name: str) -> bytes:
    """데모 아이콘 — 참조 item.png 의 아이콘 칸(116²)을 그대로 잘라낸 PNG.

    같은 렌더러가 만든 칸이라 factor=1 로 재배치되어 원본과 픽셀 동일하게 얹힌다.
    """
    return (_ICONS / f"{name}.png").read_bytes()


def build_exp() -> bytes:
    """/경험치 선 그래프 — 5명 × 7일, 절대레벨(level + exp%/100).

    성장 속도가 달라 선이 서로 겹쳤다 역전되도록 구성(불꽃아크·바람궁수가 홍길동전사를
    후반 추월, 이글루법사가 캐논슈터를 초반 추월). 순위 경쟁의 재미를 보여준다.
    """
    days = [date(2026, 6, 25) + timedelta(days=i) for i in range(7)]
    tracks: dict[str, list[float]] = {
        "홍길동전사": [271.20, 272.10, 272.60, 273.00, 273.30, 273.50, 273.60],
        "불꽃아크": [269.50, 270.40, 271.50, 272.30, 273.10, 273.80, 274.40],
        "바람궁수": [270.30, 270.60, 270.90, 271.60, 272.50, 273.20, 273.90],
        "이글루법사": [267.50, 268.40, 269.30, 270.10, 270.90, 271.80, 272.60],
        "캐논슈터": [268.20, 268.90, 269.40, 269.80, 270.10, 270.40, 270.70],
    }
    series = {
        nick: [(d, v) for d, v in zip(days, track)] for nick, track in tracks.items()
    }
    return render_progress_graph(series, ref_date=days[-1]).getvalue()


def build_spec() -> bytes:
    """/스펙 비교표 — 전투력 + HEXA 코어 격자(NumGrid) + 스탯 코어 3종."""
    core_cols = (("스킬", 2), ("마스터리", 4), ("강화", 4), ("공용", 3))
    stat_cols = ("스탯 코어 I", "스탯 코어 II", "스탯 코어 III")
    headers = ["순위", "캐릭터", "전투력", *(name for name, _ in core_cols), *stat_cols]
    aligns = ["center", "left", "left", *(["center"] * (len(headers) - 3))]
    # 스탯 코어 3종은 각 칸 합이 20(첫 칸=메인, 볼드). 전투력은 5억 이하.
    rows = [
        [
            "1",
            "홍길동전사",
            Highlight("4.8억"),
            NumGrid((30, 30), 2),
            NumGrid((30, 28, 25, 20), 4),
            NumGrid((30, 30, 28, 24), 4),
            NumGrid((30, 22, 10), 3),
            NumGrid((8, 7, 5), 3, bold_first=True, highlight_first=True),
            NumGrid((7, 9, 4), 3, bold_first=True, highlight_first=True),
            NumGrid((8, 6, 6), 3, bold_first=True, highlight_first=True),
        ],
        [
            "2",
            "불꽃아크",
            "4.1억",
            NumGrid((30, 28), 2),
            NumGrid((30, 25, 22, 18), 4),
            NumGrid((30, 28, 25, 20), 4),
            NumGrid((28, 20, 8), 3),
            NumGrid((6, 8, 6), 3, bold_first=True),
            NumGrid((5, 9, 6), 3, bold_first=True),
            NumGrid((7, 8, 5), 3, bold_first=True),
        ],
        [
            "3",
            "바람궁수",
            "3.2억",
            NumGrid((28, 25), 2),
            NumGrid((28, 22, 18, 15), 4),
            NumGrid((28, 25, 20, 16), 4),
            NumGrid((25, 18, 6), 3),
            NumGrid((5, 10, 5), 3, bold_first=True),
            NumGrid((6, 9, 5), 3, bold_first=True),
            NumGrid((5, 8, 7), 3, bold_first=True),
        ],
    ]
    return render_table_image(headers, rows, aligns=aligns)


def build_union() -> bytes:
    """/유니온 비교표."""
    headers = ["순위", "캐릭터", "유니온", "아티팩트", "챔피언"]
    aligns = ["center", "left", "center", "center", "left"]
    rows = [
        ["1", "홍길동전사", Highlight("9353"), "51 LV", "SS(1) A(2)"],
        ["2", "불꽃아크", "9333", Highlight("53 LV"), "SSS(1) S(1)"],
        ["3", "바람궁수", "9205", "50 LV", "A(3)"],
        ["4", "이글루법사", "8946", "37 LV", "B(2)"],
    ]
    return render_table_image(headers, rows, aligns=aligns)


def build_starforce() -> bytes:
    """/스타포스 비교표 — 대상=디스코드 유저(계정 합산), 10성 이상만 집계(ADR-0016)."""
    headers = ["순위", "대상", "운빨수치", "총 사용 메소", "기준건수"]
    aligns = ["center", "left", "right", "right", "right"]
    rows = [
        ["1", "홍길동전사", Highlight("상위 8%"), "62.1억", "98건"],
        ["2", "불꽃아크", "상위 34%", "63.8억", "142건"],
        ["3", "바람궁수", "상위 61%", "66.7억", "215건"],
    ]
    return render_table_image(headers, rows, aligns=aligns)


def build_potential() -> bytes:
    """/잠재 비교표 — 등업 컬럼은 색 뱃지(GradeBadges), 없으면 '—'."""
    headers = [
        "순위",
        "대상",
        "잠재 재설정",
        "사용 큐브",
        "사용 메소",
        "잠재 등업",
        "에디 등업",
    ]
    aligns = ["center", "left", "right", "right", "right", "left", "left"]
    # 잠재 재설정 > 사용 큐브(메소 재설정 포함). 사용 메소 = (재설정 - 큐브) × 8000만.
    rows = [
        [
            "1",
            "홍길동전사",
            "480",
            "380",
            Highlight("80억"),  # (480-380)×8000만
            GradeBadges((("레전드리", 1), ("유니크", 2))),
            GradeBadges((("유니크", 1),)),
        ],
        [
            "2",
            "불꽃아크",
            "265",
            "190",
            "60억",  # (265-190)×8000만
            GradeBadges((("유니크", 1),)),
            "—",
        ],
        ["3", "바람궁수", "145", "95", "40억", "—", "—"],  # (145-95)×8000만
    ]
    return render_table_image(headers, rows, aligns=aligns)


def build_item() -> bytes:
    """/아이템 카드 — 같은 부위(모자)를 네 명이 비교하는 카드 스택.

    실제 봇 출력(item.png)을 그대로 재현하되 캐릭터 이름만 데모 캐스트로 치환.
    아이콘은 참조 item.png 의 아이콘 칸을 잘라 그대로 얹는다(site/scripts/icons/).
    """
    cards = [
        ItemCard(
            label="바람궁수 · 모자",
            found=True,
            icon_png=_icon("hat_archer"),
            item_name="에테르넬 아처햇",
            starforce="17",
            potential=CardPotential(
                "레전드리", ("스킬 재사용 대기시간 -3초", "최대 HP +10%")
            ),
            additional=CardPotential("에픽", ("LUK +15", "공격력 +11", "INT +3%")),
            add_option="DEX +107, INT +77, LUK +42, 올스탯 +5%",
            upgrade="주문서 12회",
            upgrade_stats="STR +23, DEX +28, LUK +17, 공격력 +33",
        ),
        ItemCard(
            label="불꽃아크 · 모자",
            found=True,
            icon_png=_icon("hat_warrior_a"),
            item_name="하이네스 워리어헬름",
            starforce="19",
            potential=CardPotential(
                "레전드리", ("스킬 재사용 대기시간 -3초", "최대 HP +9%")
            ),
            additional=CardPotential("에픽", ("공격력 +21", "이동속도 +6")),
            add_option="STR +76, LUK +28, 올스탯 +6%",
            upgrade="주문서 12회",
            upgrade_stats="STR +29, DEX +22, INT +17, 공격력 +25, 마력 +17",
        ),
        ItemCard(
            label="홍길동전사 · 모자",
            found=True,
            icon_png=_icon("hat_warrior_b"),
            item_name="하이네스 워리어헬름",
            starforce="21",
            potential=CardPotential(
                "레전드리", ("스킬 재사용 대기시간 -2초", "STR +12%", "최대 HP +9%")
            ),
            additional=CardPotential("에픽", ("STR +4%", "STR +10", "공격력 +10")),
            add_option="STR +72, INT +24, 올스탯 +5%, 공격력 +5",
            upgrade="주문서 12회",
            upgrade_stats="STR +26, DEX +23, INT +23, LUK +29, 공격력 +26",
        ),
        ItemCard(
            label="이글루법사 · 모자",
            found=True,
            icon_png=_icon("hat_assassin"),
            item_name="하이네스 어새신보닛",
            starforce="16",
            potential=CardPotential("에픽", ("LUK +9%", "최대 HP +3%")),
            additional=CardPotential("레어", ("공격력 +10", "최대 MP +60", "INT +6")),
            add_option="LUK +40, 올스탯 +5%, HP +1800, MP +1350",
        ),
    ]
    return render_item_cards(cards)


def _write(name: str, data: bytes) -> None:
    path = _OUT / name
    path.write_bytes(data)
    print(f"  ✓ {path.relative_to(_ROOT)}  ({len(data):,} bytes)")


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    print(f"데모 스크린샷 생성 → {_OUT.relative_to(_ROOT)}")
    _write("exp.png", build_exp())
    _write("spec.png", build_spec())
    _write("union.png", build_union())
    _write("starforce.png", build_starforce())
    _write("potential.png", build_potential())
    _write("item.png", build_item())
    print("완료.")


if __name__ == "__main__":
    main()
