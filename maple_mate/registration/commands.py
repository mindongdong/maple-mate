"""등록/관리 디스코드 어댑터 (얇은 전달 계층). 로직은 service 가 담당.

멀티 캐릭터 모델(작업지시서): `/등록`(닉+키 한 방)을 4개로 분리했다.
- `/캐릭터등록 닉네임` — 메이플 캐릭터를 등록(유저당 N개, 상한 10).
- `/키등록 api키` — 개인 API 키 등록(유저당 1개, 이력류 조회 개방).
- `/대표지정 캐릭터` — 공개 명령(스펙·경험치 등)에 쓸 대표 캐릭터 지정(본인 캐릭터 자동완성).
- `/캐릭터목록` — 등록 캐릭터·레벨·대표·키 등록 여부(ephemeral) + 관리 허브(삭제·대표 변경·키 삭제, ADR-0023).

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
    await interaction.followup.send(
        embed=make_embed(
            "키 등록 완료",
            "개인 API 키를 등록했어요. 스타포스·잠재 등 **이력류**(계정 전체)를 조회할 수 있어요.",
        ),
        ephemeral=True,
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


class CharacterManageView(discord.ui.View):
    def __init__(
        self,
        deps: Deps,
        *,
        scope: int,
        user_id: int,
        characters: list[service.CharacterInfo],
        has_key: bool,
    ) -> None:
        super().__init__(timeout=_MANAGE_TIMEOUT)
        self._deps = deps
        self._scope = scope
        self._user_id = user_id
        self.characters = characters
        self.has_key = has_key
        self.busy = False  # DB 작업 진행 중(연타·중복 실행 방지)
        self._pending: list[str] = []  # 삭제 확인 대기 ocid
        self.message: discord.Message | None = None
        self._last_interaction: discord.Interaction | None = None
        self._render_hub()

    # ── 상태별 컴포넌트 ────────────────────────────────────────────────────

    def _button(self, label: str, style, callback, *, disabled=False):
        button = discord.ui.Button(label=label, style=style, disabled=disabled)
        button.callback = callback  # type: ignore[method-assign]
        self.add_item(button)
        return button

    def _select(self, callback, *, placeholder: str, options, max_values: int = 1):
        select = discord.ui.Select(
            placeholder=placeholder,
            min_values=1,
            max_values=max_values,
            options=options,
        )
        select.callback = callback  # type: ignore[method-assign]
        self.add_item(select)

    def _render_hub(self) -> None:
        self.clear_items()
        none = not self.characters
        red, grey = discord.ButtonStyle.danger, discord.ButtonStyle.secondary
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

    def _render_confirm(self, label: str, callback) -> None:
        self.clear_items()
        self._button(label, discord.ButtonStyle.danger, callback)
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
            self._render_hub()
            await interaction.edit_original_response(embed=self._embed(note), view=self)
        except Exception:
            log.exception("캐릭터 관리 작업 실패")
            self._pending = []
            self._render_hub()
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

    async def _reload(self) -> None:
        sf = self._deps.session_factory
        self.characters = await service.get_characters(sf, self._scope, self._user_id)
        self.has_key = await service.has_personal_key(sf, self._scope, self._user_id)

    # ── 콜백 ───────────────────────────────────────────────────────────────

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self._pending = []
        self._render_hub()
        await self._show(interaction, None)

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

    async def on_timeout(self) -> None:
        """컴포넌트 제거 — 마지막 클릭 토큰 우선(원 명령 토큰은 15분 뒤 만료)."""
        try:
            if self._last_interaction is not None:
                await self._last_interaction.edit_original_response(view=None)
            elif self.message is not None:
                await self.message.edit(view=None)
        except discord.HTTPException:
            pass


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
        description="넥슨 개인 API 키를 등록합니다 (스타포스·잠재 등 이력류 조회 개방).",
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
        description="등록 캐릭터·대표·키를 보고 삭제·대표 변경·키 삭제를 합니다 (본인만 보임).",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @cooldowns.spec_cooldown()
    async def character_list_command(interaction: discord.Interaction) -> None:
        await handle_character_list(deps, interaction)
