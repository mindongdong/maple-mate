"""출력 헬퍼 (빌드 단위 #6, design §7).

- 임베드 통일(`make_embed`)
- 데이터 기준 시점 푸터(`format_footer`) — 지난날짜=YYYY-MM-DD / 오늘(KST)=HH:MM 기준
- 버튼 페이지네이션(`EmbedPaginator`)
- defer 헬퍼(`defer`)

`format_footer` 는 순수함수라 단위테스트 대상. 나머지는 discord.py 래핑.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import discord

KST = timezone(timedelta(hours=9))
BRAND_COLOR = discord.Color.from_rgb(255, 140, 0)  # 메이플 오렌지


def format_footer(reference: date | datetime, now: datetime) -> str:
    """데이터 기준 시점 푸터 문자열.

    - reference 가 (KST) 오늘이면 'HH:MM 기준' (datetime 이면 그 시각, date 면 now 의 시각).
    - 그 외(지난 날짜)면 'YYYY-MM-DD'.
    """
    now_kst = now.astimezone(KST)
    if isinstance(reference, datetime):
        ref_kst = reference.astimezone(KST)
        if ref_kst.date() == now_kst.date():
            return f"{ref_kst:%H:%M} 기준"
        return ref_kst.date().isoformat()
    # date
    if reference == now_kst.date():
        return f"{now_kst:%H:%M} 기준"
    return reference.isoformat()


def make_embed(
    title: str | None = None,
    description: str | None = None,
    *,
    color: discord.Color = BRAND_COLOR,
    footer: str | None = None,
) -> discord.Embed:
    """프로젝트 공통 스타일 임베드."""
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed


async def defer(interaction: discord.Interaction, *, ephemeral: bool = False) -> None:
    """지연 응답(design §7: 비교 명령 defer 의무). 이미 응답했으면 무시."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)


class EmbedPaginator(discord.ui.View):
    """버튼 페이지네이션 (design §7: 초과 인원 버튼 페이지네이션).

    여러 임베드를 이전/다음 버튼으로 넘긴다. author_id 지정 시 작성자만 조작 가능.
    """

    def __init__(
        self,
        pages: list[discord.Embed],
        *,
        author_id: int | None = None,
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)
        if not pages:
            raise ValueError("pages 가 비어 있습니다")
        self._pages = pages
        self._index = 0
        self._author_id = author_id
        self._sync_buttons()

    @property
    def current(self) -> discord.Embed:
        return self._pages[self._index]

    def _sync_buttons(self) -> None:
        single = len(self._pages) <= 1
        self.prev_button.disabled = single or self._index == 0
        self.next_button.disabled = single or self._index == len(self._pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._author_id is not None and interaction.user.id != self._author_id:
            await interaction.response.send_message("본인만 조작할 수 있어요.", ephemeral=True)
            return False
        return True

    async def _show(self, interaction: discord.Interaction) -> None:
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current, view=self)

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self._index = max(0, self._index - 1)
        await self._show(interaction)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self._index = min(len(self._pages) - 1, self._index + 1)
        await self._show(interaction)
