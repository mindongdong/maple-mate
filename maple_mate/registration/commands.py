"""등록/관리 디스코드 어댑터 (얇은 전달 계층). 로직은 service 가 담당.

멀티 캐릭터 모델(작업지시서): `/등록`(닉+키 한 방)을 4개로 분리했다.
- `/캐릭터등록 닉네임` — 메이플 캐릭터를 등록(유저당 N개, 상한 10).
- `/키등록 api키` — 개인 API 키 등록(유저당 1개, 이력류 조회 개방) → 성공 시 계정 동기화 화면(ADR-0025).
- `/대표지정 캐릭터` — 공개 명령(스펙·경험치 등)에 쓸 대표 캐릭터 지정(본인 캐릭터 자동완성).
- `/캐릭터목록` — 등록 캐릭터·레벨·대표·키 등록 여부(ephemeral) + 관리 허브(계정 동기화·삭제·대표 변경·키 삭제,
  ADR-0023·0025).

개인 키 노출 최소화를 위해 응답은 항상 ephemeral.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..bot.scope import MSG_UNAVAILABLE, resolve_scope
from ..dependencies import Deps
from . import service
from .realm import is_challengers

log = logging.getLogger(__name__)


def _char_label(nickname: str, level: int | None, world: str | None = None) -> str:
    """`닉 (Lv.260, 챌린저스3)`. 챌린저스만 realm 표기(본서버는 무표기 — 시각 회귀 0)."""
    parts: list[str] = []
    if level is not None:
        parts.append(f"Lv.{level}")
    if is_challengers(world):
        parts.append(world)  # 예: 챌린저스3
    return f"{nickname} ({', '.join(parts)})" if parts else nickname


def character_choices(
    characters: list[service.CharacterInfo], current: str
) -> list[app_commands.Choice[str]]:
    """본인 캐릭터 목록 → 자동완성 Choice(순수함수 — `/대표지정`·`/내캐릭터` 공유).

    닉 부분일치(대소문자 무시) 필터, 라벨 = `닉 (Lv, 챌린저스N)` + 대표 👑, 상한 25(디스코드).
    value = ocid.
    """
    needle = current.strip().lower()
    choices: list[app_commands.Choice[str]] = []
    for c in characters:
        if needle and needle not in c.nickname.lower():
            continue
        label = _char_label(c.nickname, c.level, c.world)
        if c.is_representative:
            label = f"{label} 👑"
        choices.append(app_commands.Choice(name=label[:100], value=c.ocid))
        if len(choices) >= 25:  # Discord 자동완성 옵션 상한
            break
    return choices


async def handle_character_register(
    deps: Deps, interaction: discord.Interaction, nickname: str
) -> None:
    await defer(interaction, ephemeral=True)
    scope = resolve_scope(interaction)
    if scope is None:
        await interaction.followup.send(
            embed=make_embed("캐릭터 등록 실패", MSG_UNAVAILABLE), ephemeral=True
        )
        return

    result = await service.register_character(
        nexon=deps.nexon,
        session_factory=deps.session_factory,
        guild_id=scope,
        discord_user_id=interaction.user.id,
        nickname=nickname.strip(),
    )
    if not result.ok:
        await interaction.followup.send(
            embed=make_embed("캐릭터 등록 실패", result.error), ephemeral=True
        )
        return

    has_key = await service.has_personal_key(
        deps.session_factory, scope, interaction.user.id
    )
    lines = [
        f"**{_char_label(result.nickname, result.level)}** 등록 완료 — 현재 {result.character_count}개.",
    ]
    if result.character_count == 1:
        lines.append("이 캐릭터가 대표예요. `/대표지정`으로 바꿀 수 있어요.")
    else:
        lines.append(
            "대표는 등록 캐릭터 중 최고 레벨이에요. `/대표지정`으로 바꿀 수 있어요."
        )
    if not has_key:
        lines.append(
            "스타포스·잠재 등 **이력류**를 보려면 `/키등록`으로 개인 키를 등록하세요."
        )
    await interaction.followup.send(
        embed=make_embed("캐릭터 등록 완료", "\n".join(lines)), ephemeral=True
    )


async def handle_key_register(
    deps: Deps, interaction: discord.Interaction, api_key: str
) -> None:
    await defer(interaction, ephemeral=True)
    scope = resolve_scope(interaction)
    if scope is None:
        await interaction.followup.send(
            embed=make_embed("키 등록 실패", MSG_UNAVAILABLE), ephemeral=True
        )
        return

    result = await service.register_key(
        nexon=deps.nexon,
        cipher=deps.cipher,
        session_factory=deps.session_factory,
        guild_id=scope,
        discord_user_id=interaction.user.id,
        api_key=api_key.strip(),
    )
    if not result.ok:
        await interaction.followup.send(
            embed=make_embed("키 등록 실패", result.error), ephemeral=True
        )
        return
    # 키 등록 직후 계정 동기화 화면을 바로 띄운다(ADR-0025) — 조회 실패해도 키 등록은 성공으로 유지.
    embed, view = await build_account_sync(
        deps,
        scope,
        interaction.user.id,
        header=(
            "🔑 개인 API 키를 등록했어요. 스타포스·잠재 등 **이력류**(계정 전체)를 "
            "조회할 수 있어요."
        ),
    )
    if view is None:
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    view.message = await interaction.followup.send(
        embed=embed, view=view, ephemeral=True, wait=True
    )


async def handle_set_representative(
    deps: Deps, interaction: discord.Interaction, ocid: str
) -> None:
    await defer(interaction, ephemeral=True)
    scope = resolve_scope(interaction)
    if scope is None:
        await interaction.followup.send(
            embed=make_embed("대표 지정 실패", MSG_UNAVAILABLE), ephemeral=True
        )
        return

    nickname = await service.set_representative(
        deps.session_factory, scope, interaction.user.id, ocid
    )
    if nickname is None:
        await interaction.followup.send(
            embed=make_embed(
                "대표 지정 실패",
                "본인 등록 캐릭터가 아니에요. `/캐릭터목록`에서 확인해 주세요.",
            ),
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        embed=make_embed(
            "대표 지정 완료",
            f"대표 캐릭터를 **{nickname}** 으로 지정했어요. 스펙·경험치 등 공개 명령에 반영돼요.",
        ),
        ephemeral=True,
    )


_NO_CHARACTERS = "등록된 캐릭터가 없어요. `/캐릭터등록`으로 먼저 등록해 주세요."


def character_list_embed(
    characters: list[service.CharacterInfo], has_key: bool, note: str | None = None
) -> discord.Embed:
    """`/캐릭터목록` 허브 임베드(순수) — 안내/결과 줄(note) + 캐릭터 목록 + 키 상태."""
    lines = [note, ""] if note else []
    if characters:
        for c in characters:
            mark = " 👑 대표" if c.is_representative else ""
            lines.append(f"• {_char_label(c.nickname, c.level, c.world)}{mark}")
    else:
        lines.append(_NO_CHARACTERS)
    lines.append("")
    lines.append(
        "개인 키: 등록됨 (이력류 조회 가능)"
        if has_key
        else "개인 키: 미등록 (`/키등록`으로 이력류 조회 개방)"
    )
    return make_embed(
        f"캐릭터 목록 ({len(characters)}/{service.MAX_CHARACTERS_PER_USER})",
        "\n".join(lines),
    )


# ── 관리 허브 View (ADR-0023) ───────────────────────────────────────────────
#
# `/캐릭터목록`(ephemeral) 아래 버튼: 캐릭터 삭제 · 대표 변경 · 키 삭제. 파괴적 작업(삭제·키 삭제)은
# 확인 단계를 한 번 더 거친다. 상태(mode)마다 컴포넌트를 다시 그려 같은 메시지를 교체한다.

_MANAGE_TIMEOUT = 300.0
_AUTO_REP = "__auto__"  # 대표 변경 Select 의 '자동(최고 레벨)' 값 — ocid 와 충돌 불가


class _ManagedView(discord.ui.View):
    """관리 화면 공통 — 같은 메시지를 상태별로 다시 그리고, DB 작업은 먼저 응답 후 처리한다(ADR-0023 결정 8).

    하위 클래스가 `_embed(note)`·`_reload()`·`_render_home()` 를 구현한다.
    """

    def __init__(self, deps: Deps, *, scope: int, user_id: int) -> None:
        super().__init__(timeout=_MANAGE_TIMEOUT)
        self._deps = deps
        self._scope = scope
        self._user_id = user_id
        self.busy = False  # DB 작업 진행 중(연타·중복 실행 방지)
        self._pending: list[str] = []  # 확인 대기 ocid
        self.message: discord.Message | None = None
        self._last_interaction: discord.Interaction | None = None

    def _button(self, label: str, style, callback, *, disabled=False):
        button = discord.ui.Button(label=label, style=style, disabled=disabled)
        button.callback = callback  # type: ignore[method-assign]
        self.add_item(button)
        return button

    def _select(
        self,
        callback,
        *,
        placeholder: str,
        options,
        max_values: int = 1,
        min_values: int = 1,
        disabled: bool = False,
    ):
        select = discord.ui.Select(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            disabled=disabled,
        )
        select.callback = callback  # type: ignore[method-assign]
        self.add_item(select)

    def _render_confirm(self, label: str, callback) -> None:
        self.clear_items()
        self._button(label, discord.ButtonStyle.danger, callback)
        self._button("취소", discord.ButtonStyle.secondary, self._cancel)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self._pending = []
        self._render_home()
        await self._show(interaction, None)

    async def _show(self, interaction: discord.Interaction, note: str | None) -> None:
        """DB 작업 없는 화면 전환 — 즉시 같은 메시지 교체. 작업 진행 중이면 조용히 확인만."""
        if self.busy:
            await interaction.response.defer()
            return
        self._last_interaction = interaction
        await interaction.response.edit_message(embed=self._embed(note), view=self)

    async def _act(
        self,
        interaction: discord.Interaction,
        action: Callable[[], Awaitable[str]],
    ) -> None:
        """DB 작업: 진행 중 클릭은 무시 → 즉시 전체 비활성으로 응답(3초 기한) → 작업·재조회 →
        허브로 결과 반영. 응답을 먼저 해 DB 가 느려도 상호작용이 만료되지 않는다."""
        if self.busy:
            await interaction.response.defer()
            return
        self.busy = True
        self._last_interaction = interaction
        done = False  # 작업 자체는 커밋됐는지 — 이후 화면 갱신만 실패한 경우를 구분
        try:
            for item in self.children:
                item.disabled = True  # type: ignore[attr-defined]
            await interaction.response.edit_message(view=self)
            note = await action()
            done = True
            await self._reload()
            self._render_home()
            await interaction.edit_original_response(embed=self._embed(note), view=self)
        except Exception:
            log.exception("캐릭터 관리 작업 실패")
            self._pending = []
            self._render_home()
            message = (
                "✅ 처리는 완료됐지만 화면을 갱신하지 못했어요. `/캐릭터목록`을 다시 열어 주세요."
                if done
                else "⚠️ 처리 중 오류가 났어요. 다시 시도해 주세요."
            )
            try:
                await interaction.edit_original_response(
                    embed=self._embed(message), view=self
                )
            except discord.HTTPException:
                pass
        finally:
            self.busy = False

    async def on_timeout(self) -> None:
        """컴포넌트 제거 — 마지막 클릭 토큰 우선(원 명령 토큰은 15분 뒤 만료)."""
        try:
            if self._last_interaction is not None:
                await self._last_interaction.edit_original_response(view=None)
            elif self.message is not None:
                await self.message.edit(view=None)
        except discord.HTTPException:
            pass


class CharacterManageView(_ManagedView):
    def __init__(
        self,
        deps: Deps,
        *,
        scope: int,
        user_id: int,
        characters: list[service.CharacterInfo],
        has_key: bool,
    ) -> None:
        super().__init__(deps, scope=scope, user_id=user_id)
        self.characters = characters
        self.has_key = has_key
        self._render_home()

    # ── 상태별 컴포넌트 ────────────────────────────────────────────────────

    def _render_home(self) -> None:
        self.clear_items()
        none = not self.characters
        red, grey = discord.ButtonStyle.danger, discord.ButtonStyle.secondary
        self._button(
            "🔄 계정 동기화",
            discord.ButtonStyle.primary,
            self._open_sync,
            disabled=not self.has_key,
        )
        self._button("🗑️ 캐릭터 삭제", red, self._open_delete, disabled=none)
        self._button("👑 대표 변경", grey, self._open_rep, disabled=none)
        self._button("🔑 키 삭제", red, self._open_key, disabled=not self.has_key)

    def _render_delete_select(self) -> None:
        self.clear_items()
        self._select(
            self._picked_delete,
            placeholder="삭제할 캐릭터 선택 (여러 개 가능)",
            options=[_character_option(c) for c in self.characters],
            max_values=len(self.characters),
        )
        self._button("취소", discord.ButtonStyle.secondary, self._cancel)

    def _render_rep_select(self) -> None:
        self.clear_items()
        self._select(
            self._picked_rep,
            placeholder="대표 캐릭터 선택",
            options=[
                discord.SelectOption(
                    label="자동 (등록 캐릭터 중 최고 레벨)", value=_AUTO_REP
                ),
                *(_character_option(c) for c in self.characters),
            ],
        )
        self._button("취소", discord.ButtonStyle.secondary, self._cancel)

    def _embed(self, note: str | None) -> discord.Embed:
        return character_list_embed(self.characters, self.has_key, note)

    async def _reload(self) -> None:
        sf = self._deps.session_factory
        self.characters = await service.get_characters(sf, self._scope, self._user_id)
        self.has_key = await service.has_personal_key(sf, self._scope, self._user_id)

    # ── 콜백 ───────────────────────────────────────────────────────────────

    async def _open_sync(self, interaction: discord.Interaction) -> None:
        """계정 동기화 화면으로 전환(넥슨 1콜) — 먼저 응답한 뒤 같은 메시지를 동기화 View 로 교체."""
        if self.busy:
            await interaction.response.defer()
            return
        self.busy = True
        try:
            await interaction.response.defer()
            embed, view = await build_account_sync(
                self._deps, self._scope, self._user_id, back=True
            )
            if view is None:  # 조회 실패 — 허브 유지 + 사유 안내
                self._last_interaction = interaction
                await interaction.edit_original_response(embed=embed, view=self)
                return
            view._last_interaction = interaction
            self.stop()  # 허브 타임아웃이 동기화 화면을 지우지 않도록
            await interaction.edit_original_response(embed=embed, view=view)
        finally:
            self.busy = False

    async def _open_delete(self, interaction: discord.Interaction) -> None:
        self._render_delete_select()
        await self._show(interaction, "🗑️ 삭제할 캐릭터를 골라 주세요.")

    async def _picked_delete(self, interaction: discord.Interaction) -> None:
        self._pending = _selected_values(interaction)
        names = ", ".join(
            c.nickname for c in self.characters if c.ocid in self._pending
        )
        self._render_confirm(f"{len(self._pending)}개 삭제", self._confirm_delete)
        await self._show(
            interaction,
            f"⚠️ **{names}** 을(를) 삭제할까요? 다시 쓰려면 `/캐릭터등록`으로 재등록해요.",
        )

    async def _confirm_delete(self, interaction: discord.Interaction) -> None:
        pending, self._pending = self._pending, []
        was_rep = any(
            c.is_representative and c.ocid in pending for c in self.characters
        )

        async def action() -> str:
            removed, unsubscribed = await service.delete_characters(
                self._deps.session_factory, self._scope, self._user_id, pending
            )
            if not removed:
                return "이미 삭제됐거나 본인 캐릭터가 아니에요."
            note = f"🗑️ **{', '.join(removed)}** 삭제했어요."
            if unsubscribed:
                note += " 남은 캐릭터가 없어 스케줄러알림 구독도 해제했어요."
            elif was_rep:
                note += " 대표는 남은 캐릭터 중 최고 레벨로 자동 선택돼요."
            return note

        await self._act(interaction, action)

    async def _open_rep(self, interaction: discord.Interaction) -> None:
        self._render_rep_select()
        await self._show(interaction, "👑 대표 캐릭터를 골라 주세요.")

    async def _picked_rep(self, interaction: discord.Interaction) -> None:
        [value] = _selected_values(interaction)

        async def action() -> str:
            sf = self._deps.session_factory
            if value == _AUTO_REP:
                await service.reset_representative(sf, self._scope, self._user_id)
                return "👑 대표를 자동(최고 레벨)으로 되돌렸어요."
            nickname = await service.set_representative(
                sf, self._scope, self._user_id, value
            )
            if nickname is None:
                return "이미 삭제됐거나 본인 캐릭터가 아니에요."
            return f"👑 대표를 **{nickname}** 으로 지정했어요."

        await self._act(interaction, action)

    async def _open_key(self, interaction: discord.Interaction) -> None:
        self._render_confirm("키 삭제", self._confirm_key)
        await self._show(
            interaction,
            "⚠️ 개인 키를 삭제할까요? 저장된 스타포스·잠재 조회 기록도 함께 지워지고, "
            "스타포스·잠재·스케줄러 조회가 막히며 **스케줄러알림 구독도 해제**돼요. "
            "등록 캐릭터는 그대로 남아요.",
        )

    async def _confirm_key(self, interaction: discord.Interaction) -> None:
        async def action() -> str:
            had_key, unsubscribed = await service.remove_personal_key(
                self._deps.session_factory,
                self._deps.cipher,
                self._scope,
                self._user_id,
            )
            note = (
                "🔑 개인 키와 이 계정의 스타포스·잠재 조회 기록을 삭제했어요."
                if had_key
                else "이미 키가 없어요."
            )
            if unsubscribed:
                note += " 스케줄러알림 구독도 해제했어요."
            return note

        await self._act(interaction, action)


# ── 계정 동기화 View (ADR-0025) ───────────────────────────────────────────────
#
# 진입: `/캐릭터목록` 허브 `🔄 계정 동기화` · `/키등록` 성공 직후. 넥슨 `character/list` 1콜로 받은 목록을
# View 가 들고 있고, 페이지 이동·선택은 그 안에서만 처리한다(추가 호출 0).

_SYNC_PAGE = 5  # 한 페이지 후보 수(레벨 높은 순)


class AccountSyncView(_ManagedView):
    def __init__(
        self,
        deps: Deps,
        *,
        scope: int,
        user_id: int,
        account: list[service.AccountCharacter],
        registered: list[service.CharacterInfo],
        updated: int,
        back: bool = False,
        header: str | None = None,
    ) -> None:
        super().__init__(deps, scope=scope, user_id=user_id)
        self.account = account
        self.registered = registered
        self.updated = updated  # 열 때 자동 갱신한 등록 캐릭터 수
        self._back = back  # True 면 '← 목록으로'(허브 복귀), 아니면 '닫기'
        self._header = header
        self.page = 0
        self.picked: dict[str, service.AccountCharacter] = {}  # 페이지를 넘어도 유지
        self._recompute()
        self._render_home()

    # ── 상태 ───────────────────────────────────────────────────────────────

    def _recompute(self) -> None:
        self.plan = service.plan_sync(self.registered, self.account)
        candidate_ocids = {c.ocid for c in self.plan.candidates}
        kept = [(o, c) for o, c in self.picked.items() if o in candidate_ocids]
        # 다른 경로 등록으로 자리가 줄었을 수 있어 남은 자리까지만 유지
        self.picked = dict(kept[: self.room])
        self.page = min(self.page, max(self.pages - 1, 0))

    @property
    def pages(self) -> int:
        return -(-len(self.plan.candidates) // _SYNC_PAGE)

    @property
    def room(self) -> int:
        """가져올 수 있는 남은 자리(등록 상한 − 현재 등록 수)."""
        return max(service.MAX_CHARACTERS_PER_USER - len(self.registered), 0)

    def _page_items(self) -> list[service.AccountCharacter]:
        start = self.page * _SYNC_PAGE
        return self.plan.candidates[start : start + _SYNC_PAGE]

    # ── 렌더 ───────────────────────────────────────────────────────────────

    def _render_home(self) -> None:
        self.clear_items()
        grey = discord.ButtonStyle.secondary
        items = self._page_items()
        if items:
            on_page = {c.ocid for c in items}
            allowed = self.room - len([o for o in self.picked if o not in on_page])
            self._select(
                self._picked_import,
                placeholder=(
                    "가져올 캐릭터 선택 (여러 개 가능)"
                    if allowed > 0
                    else "남은 자리가 없어요 — 선택을 줄이거나 캐릭터를 정리해 주세요"
                ),
                options=[
                    discord.SelectOption(
                        label=f"{c.nickname} · Lv.{c.level or '?'} · {c.world or '?'}"[
                            :100
                        ],
                        description=(c.job or None),
                        value=c.ocid,
                        default=c.ocid in self.picked,
                    )
                    for c in items
                ],
                min_values=0,
                max_values=max(min(len(items), allowed), 1),
                disabled=allowed <= 0,
            )
            self._button("◀ 이전", grey, self._prev, disabled=self.page == 0)
            self._button(
                f"{self.page + 1} / {self.pages}", grey, self._noop, disabled=True
            )
            self._button(
                "다음 ▶", grey, self._next, disabled=self.page >= self.pages - 1
            )
        self._button(
            f"✅ {len(self.picked)}개 가져오기",
            discord.ButtonStyle.success,
            self._confirm_import,
            disabled=not self.picked,
        )
        if self.plan.missing:
            self._button(
                f"🧹 계정에 없는 캐릭터 정리 ({len(self.plan.missing)})",
                grey,
                self._open_cleanup,
            )
        self._button("← 목록으로" if self._back else "닫기", grey, self._leave)

    def _render_cleanup(self) -> None:
        self.clear_items()
        self._select(
            self._picked_cleanup,
            placeholder="정리(삭제)할 캐릭터 선택 (여러 개 가능)",
            options=[_character_option(c) for c in self.plan.missing],
            max_values=len(self.plan.missing),
        )
        self._button("취소", discord.ButtonStyle.secondary, self._cancel)

    def _embed(self, note: str | None) -> discord.Embed:
        lines = [self._header, ""] if self._header else []
        if note:
            lines += [note, ""]
        lines.append(
            f"계정 캐릭터 {len(self.account)}개 · 등록 "
            f"{len(self.registered)}/{service.MAX_CHARACTERS_PER_USER}"
            + (f" · 닉·레벨 갱신 {self.updated}개" if self.updated else "")
        )
        if self.plan.candidates:
            lines.append(
                f"가져올 수 있는 캐릭터 {len(self.plan.candidates)}개 "
                "(레벨 높은 순 · 챌린저스 월드 제외) — 아래에서 골라 주세요."
            )
        else:
            lines.append("가져올 새 캐릭터가 없어요.")
        if self.picked:
            names = ", ".join(c.nickname for c in self.picked.values())
            lines.append(
                f"선택됨: **{names}** (남은 자리 {self.room - len(self.picked)})"
            )
        if self.plan.missing:
            names = ", ".join(c.nickname for c in self.plan.missing)
            lines.append(
                f"계정에서 찾을 수 없는 등록 캐릭터: {names} "
                "— 다른 계정 캐릭터일 수 있어 자동으로 지우지 않아요."
            )
        return make_embed("🔄 계정 동기화", "\n".join(lines))

    async def _reload(self) -> None:
        self.registered = await service.get_characters(
            self._deps.session_factory, self._scope, self._user_id
        )
        self._recompute()

    # ── 콜백 ───────────────────────────────────────────────────────────────

    async def _noop(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.page = max(self.page - 1, 0)
        self._render_home()
        await self._show(interaction, None)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.page = min(self.page + 1, self.pages - 1)
        self._render_home()
        await self._show(interaction, None)

    async def _picked_import(self, interaction: discord.Interaction) -> None:
        on_page = {c.ocid: c for c in self._page_items()}
        chosen = [o for o in _selected_values(interaction) if o in on_page]
        self.picked = {o: c for o, c in self.picked.items() if o not in on_page}
        for o in chosen[: self.room - len(self.picked)]:
            self.picked[o] = on_page[o]
        self._render_home()
        await self._show(interaction, None)

    async def _confirm_import(self, interaction: discord.Interaction) -> None:
        picks = list(self.picked.values())
        self.picked = {}

        async def action() -> str:
            added, skipped = await service.import_characters(
                self._deps.session_factory, self._scope, self._user_id, picks
            )
            if not added:
                return "가져온 캐릭터가 없어요(이미 등록됐거나 자리가 없어요)."
            note = f"✅ **{', '.join(added)}** 가져왔어요."
            if skipped:
                note += f" 자리가 없어 {skipped}개는 빠졌어요."
            return note

        await self._act(interaction, action)

    async def _open_cleanup(self, interaction: discord.Interaction) -> None:
        self._render_cleanup()
        await self._show(interaction, "🧹 정리할 캐릭터를 골라 주세요.")

    async def _picked_cleanup(self, interaction: discord.Interaction) -> None:
        self._pending = _selected_values(interaction)
        names = ", ".join(
            c.nickname for c in self.plan.missing if c.ocid in self._pending
        )
        self._render_confirm(f"{len(self._pending)}개 삭제", self._confirm_cleanup)
        await self._show(interaction, f"⚠️ **{names}** 을(를) 등록에서 삭제할까요?")

    async def _confirm_cleanup(self, interaction: discord.Interaction) -> None:
        pending, self._pending = self._pending, []

        async def action() -> str:
            removed, unsubscribed = await service.delete_characters(
                self._deps.session_factory, self._scope, self._user_id, pending
            )
            if not removed:
                return "이미 삭제됐거나 본인 캐릭터가 아니에요."
            note = f"🧹 **{', '.join(removed)}** 정리했어요."
            if unsubscribed:
                note += " 남은 캐릭터가 없어 스케줄러알림 구독도 해제했어요."
            return note

        await self._act(interaction, action)

    async def _leave(self, interaction: discord.Interaction) -> None:
        if self.busy:
            await interaction.response.defer()
            return
        self.stop()  # 이 화면의 타임아웃이 다음 화면을 지우지 않도록
        if not self._back:
            await interaction.response.edit_message(view=None)
            return
        # 허브 복귀 — 먼저 응답(3초 기한)한 뒤 재조회해 같은 메시지를 새 허브로 교체(ADR-0023 결정 8)
        await interaction.response.defer()
        try:
            sf = self._deps.session_factory
            characters = await service.get_characters(sf, self._scope, self._user_id)
            has_key = await service.has_personal_key(sf, self._scope, self._user_id)
            hub = CharacterManageView(
                self._deps,
                scope=self._scope,
                user_id=self._user_id,
                characters=characters,
                has_key=has_key,
            )
            hub._last_interaction = interaction
            await interaction.edit_original_response(
                embed=character_list_embed(characters, has_key), view=hub
            )
        except Exception:
            log.exception("캐릭터 목록 복귀 실패")
            try:
                await interaction.edit_original_response(
                    embed=self._embed(
                        "⚠️ 목록을 다시 불러오지 못했어요. `/캐릭터목록`을 다시 열어 주세요."
                    ),
                    view=None,
                )
            except discord.HTTPException:
                pass


async def build_account_sync(
    deps: Deps,
    scope: int,
    user_id: int,
    *,
    back: bool = False,
    header: str | None = None,
) -> tuple[discord.Embed, AccountSyncView | None]:
    """계정 목록 1콜 → 등록 캐릭터 자동 갱신 → 동기화 View. 실패면 (안내 임베드, None).

    예외도 안내 임베드로 바꾼다 — `/키등록` 은 이미 키를 커밋했으므로 완료 응답이 반드시 나가야 한다.
    """
    try:
        account, error = await service.fetch_account_characters(
            nexon=deps.nexon,
            cipher=deps.cipher,
            session_factory=deps.session_factory,
            guild_id=scope,
            discord_user_id=user_id,
        )
        if account is not None:
            registered = await service.get_characters(
                deps.session_factory, scope, user_id
            )
            plan = service.plan_sync(registered, account)
            if plan.updates:
                await service.apply_account_updates(
                    deps.session_factory, scope, user_id, plan.updates
                )
                registered = await service.get_characters(
                    deps.session_factory, scope, user_id
                )
            view = AccountSyncView(
                deps,
                scope=scope,
                user_id=user_id,
                account=account,
                registered=registered,
                updated=len(plan.updates),
                back=back,
                header=header,
            )
            return view._embed(None), view
    except Exception:
        log.exception("계정 동기화 준비 실패")
        error = "일시적인 오류가 났어요."
    lines = [header, ""] if header else []
    lines += [
        f"⚠️ 계정 캐릭터를 불러오지 못했어요: {error}",
        "`/캐릭터목록` → `🔄 계정 동기화`로 다시 시도할 수 있어요.",
    ]
    return make_embed("🔄 계정 동기화", "\n".join(lines)), None


def _selected_values(interaction: discord.Interaction) -> list[str]:
    """이 클릭(Select)이 실제로 보낸 값 — View 가 보관한 컴포넌트가 아니라 인터랙션 데이터에서 읽는다."""
    return list((interaction.data or {}).get("values", []))


def _character_option(c: service.CharacterInfo) -> discord.SelectOption:
    label = _char_label(c.nickname, c.level, c.world)
    if c.is_representative:
        label = f"{label} 👑"
    return discord.SelectOption(label=label[:100], value=c.ocid)


async def handle_character_list(deps: Deps, interaction: discord.Interaction) -> None:
    await defer(interaction, ephemeral=True)
    scope = resolve_scope(interaction)
    if scope is None:
        await interaction.followup.send(
            embed=make_embed("캐릭터 목록", MSG_UNAVAILABLE), ephemeral=True
        )
        return

    characters = await service.get_characters(
        deps.session_factory, scope, interaction.user.id
    )
    has_key = await service.has_personal_key(
        deps.session_factory, scope, interaction.user.id
    )
    if not characters and not has_key:  # 관리할 것이 없음 — 기존 안내 그대로
        await interaction.followup.send(
            embed=make_embed("캐릭터 목록", _NO_CHARACTERS), ephemeral=True
        )
        return

    view = CharacterManageView(
        deps,
        scope=scope,
        user_id=interaction.user.id,
        characters=characters,
        has_key=has_key,
    )
    view.message = await interaction.followup.send(
        embed=character_list_embed(characters, has_key),
        view=view,
        ephemeral=True,
        wait=True,
    )


def setup(bot: discord.Client) -> None:
    """봇 트리에 등록/관리 명령 4개를 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="캐릭터등록",
        description="메이플 캐릭터를 이 서버에 등록합니다 (유저당 여러 개 가능).",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.rename(nickname="닉네임")
    @app_commands.describe(nickname="메이플 캐릭터 닉네임")
    @cooldowns.settings_cooldown()
    async def character_register_command(
        interaction: discord.Interaction, nickname: str
    ) -> None:
        await handle_character_register(deps, interaction, nickname)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="키등록",
        description="넥슨 개인 API 키를 등록하고 계정 캐릭터를 불러옵니다 (스타포스·잠재 등 이력류 조회 개방).",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.rename(api_key="api키")
    @app_commands.describe(api_key="넥슨 개인 API 키")
    @cooldowns.settings_cooldown()
    async def key_register_command(
        interaction: discord.Interaction, api_key: str
    ) -> None:
        await handle_key_register(deps, interaction, api_key)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="대표지정",
        description="공개 명령(스펙·경험치 등)에 쓸 대표 캐릭터를 지정합니다.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.rename(ocid="캐릭터")
    @app_commands.describe(ocid="대표로 지정할 본인 등록 캐릭터")
    @cooldowns.settings_cooldown()
    async def set_representative_command(
        interaction: discord.Interaction, ocid: str
    ) -> None:
        await handle_set_representative(deps, interaction, ocid)

    @set_representative_command.autocomplete("ocid")
    async def _representative_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        scope = resolve_scope(interaction)
        if scope is None:
            return []
        characters = await service.get_characters(
            deps.session_factory, scope, interaction.user.id
        )
        return character_choices(characters, current)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="캐릭터목록",
        description="등록 캐릭터·대표·키를 보고 계정 동기화·삭제·대표 변경·키 삭제를 합니다 (본인만 보임).",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @cooldowns.spec_cooldown()
    async def character_list_command(interaction: discord.Interaction) -> None:
        await handle_character_list(deps, interaction)
