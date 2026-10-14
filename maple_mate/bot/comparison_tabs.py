"""비교 결과 탭 전환 View (ADR-0022) — `/스펙`·`/아이템`·`/유니온` 결과 메시지에 붙는다.

스펙·유니온 버튼 + 아이템 부위 Select. 실행자만 조작하고 메시지를 제자리에서 교체한다.
최초 실행 때 해석된 대상 집합(targets + 사전 실패 missing)과 무인자 안내 줄(notes)을 그대로
재사용한다(재해석·재랜덤 없음). 빌더는 핸들러가 주입한다 — 도메인(character·union)이 이미
`bot` 을 import 하므로 여기서 도메인을 import 하면 순환이 생긴다.

non-persistent(재시작 시 무효 — Bitik·페이지네이터와 같은 감수). discord.py 의 timeout 은
**마지막 클릭부터의 유휴 시간**이라 원 명령 토큰(15분)이 먼저 만료될 수 있다 → on_timeout 은
마지막 클릭 인터랙션(클릭마다 새 15분 토큰)으로 컴포넌트를 지우고, 클릭이 없었을 때만 원 메시지를 쓴다.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Literal

import discord

from ..registration.service import Target, TargetOutcome
from .comparison import ComparisonMessage

log = logging.getLogger(__name__)

Tab = Literal["spec", "item", "union"]
# (대상, 사전 실패, 안내 줄, 부위) → 메시지. 부위는 item 탭만 쓴다.
Builder = Callable[
    [list[Target], list[TargetOutcome], list[str], str | None],
    Awaitable[ComparisonMessage],
]

TABS_TIMEOUT = 600.0  # 유휴 10분 — 마지막 클릭 토큰(15분) 수명 안
# /스펙 1명당 ≈13콜 — 무인자 아이템·유니온(최대 10명)에서 넘어오면 본인 우선 5명만.
SPEC_TAB_CAP = 5
SPEC_TRUNCATED_NOTE = (
    f"스펙은 최대 {SPEC_TAB_CAP}명 — 본인 우선 {SPEC_TAB_CAP}명만 비교했어요"
)
NOT_AUTHOR = "본인만 조작할 수 있어요."


class ComparisonTabsView(discord.ui.View):
    def __init__(
        self,
        *,
        author_id: int,
        targets: Sequence[Target],
        missing: Sequence[TargetOutcome],
        notes: Sequence[str],
        current: Tab,
        slot: str | None,
        slots: Sequence[str],
        builders: Mapping[Tab, Builder],
        timeout: float = TABS_TIMEOUT,
    ) -> None:
        super().__init__(timeout=timeout)
        self._author_id = author_id
        self._targets = list(targets)
        self._missing = list(missing)
        self._notes = list(notes)
        self._builders = builders
        self.current: Tab = current
        self.slot = slot
        self.busy = False
        self.message: discord.Message | None = None
        self._last_interaction: discord.Interaction | None = None

        self.spec_button: discord.ui.Button = discord.ui.Button(label="스펙", row=0)
        self.union_button: discord.ui.Button = discord.ui.Button(label="유니온", row=0)
        self.slot_select: discord.ui.Select = discord.ui.Select(
            placeholder="아이템 부위 선택",
            row=1,
            options=[discord.SelectOption(label=s, value=s) for s in slots],
        )
        self.spec_button.callback = self._on_spec  # type: ignore[method-assign]
        self.union_button.callback = self._on_union  # type: ignore[method-assign]
        self.slot_select.callback = self._on_slot  # type: ignore[method-assign]
        for item in (self.spec_button, self.union_button, self.slot_select):
            self.add_item(item)
        self.sync_components()

    # ── 상태 → 컴포넌트 ────────────────────────────────────────────────────

    def sync_components(self) -> None:
        """현재 탭 버튼은 primary·disabled, 아이템 탭이면 그 부위를 Select 기본값으로."""
        for button, tab in ((self.spec_button, "spec"), (self.union_button, "union")):
            active = self.current == tab
            button.style = (
                discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary
            )
            button.disabled = active
        for option in self.slot_select.options:
            option.default = self.current == "item" and option.value == self.slot
        self.slot_select.disabled = False

    def _disable_all(self) -> None:
        self.spec_button.disabled = True
        self.union_button.disabled = True
        self.slot_select.disabled = True

    # ── 상호작용 ───────────────────────────────────────────────────────────

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(NOT_AUTHOR, ephemeral=True)
            return False
        return True

    async def _on_spec(self, interaction: discord.Interaction) -> None:
        await self.switch(interaction, "spec", None)

    async def _on_union(self, interaction: discord.Interaction) -> None:
        await self.switch(interaction, "union", None)

    async def _on_slot(self, interaction: discord.Interaction) -> None:
        await self.switch(interaction, "item", self.slot_select.values[0])

    async def switch(
        self, interaction: discord.Interaction, tab: Tab, slot: str | None
    ) -> None:
        """탭 교체: 즉시 전체 비활성으로 응답(3초 기한) → 조회·렌더 → 결과·재활성 반영."""
        if self.busy:  # 진행 중 클릭(연타)은 조용히 확인만
            await interaction.response.defer()
            return
        self.busy = True
        self._last_interaction = interaction
        previous = (self.current, self.slot)
        try:
            self._disable_all()
            await interaction.response.edit_message(view=self)
            targets, notes = self._targets, self._notes
            if tab == "spec" and len(targets) > SPEC_TAB_CAP:
                # 본인 먼저(안정 정렬) — 등록자 ≤10 무인자는 선정 없이 DB 순서라 본인이 뒤에
                # 있을 수 있다. 스펙 표는 전투력순이라 표시 순서엔 영향 없음.
                mine_first = sorted(
                    targets, key=lambda t: t.discord_user_id != self._author_id
                )
                targets = mine_first[:SPEC_TAB_CAP]
                notes = [*notes, SPEC_TRUNCATED_NOTE]
            message = await self._builders[tab](
                list(targets), list(self._missing), list(notes), slot
            )
            self.current, self.slot = tab, slot
            self.sync_components()
            await interaction.edit_original_response(
                embed=message.embed,
                attachments=[message.file] if message.file is not None else [],
                view=self,
            )
        except Exception:
            log.exception("비교 탭 전환 실패 (%s)", tab)
            self.current, self.slot = (
                previous  # 화면은 이전 탭 그대로 — 재시도 가능하게
            )
            self.sync_components()
            try:
                await interaction.edit_original_response(view=self)
            except discord.HTTPException:
                pass
        finally:
            self.busy = False

    async def on_timeout(self) -> None:
        """컴포넌트 제거 — 마지막 클릭 토큰 우선(원 명령 토큰은 이미 만료됐을 수 있음)."""
        try:
            if self._last_interaction is not None:
                await self._last_interaction.edit_original_response(view=None)
            elif self.message is not None:
                await self.message.edit(view=None)
        except discord.HTTPException:
            pass  # 메시지가 지워졌거나 토큰 만료

    async def send(
        self, interaction: discord.Interaction, message: ComparisonMessage
    ) -> None:
        """최초 결과를 이 View 와 함께 followup 으로 보낸다(타임아웃 정리용 메시지 핸들 보관)."""
        kwargs: dict = {"embed": message.embed, "view": self, "wait": True}
        if message.file is not None:
            kwargs["file"] = message.file
        self.message = await interaction.followup.send(**kwargs)
