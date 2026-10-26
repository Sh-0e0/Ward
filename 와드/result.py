"""/게임끝: 누구나 모든 플레이어의 KDA를 입력, 방장이 결과 확정"""
import discord

import analysis
import db
from utils import TEAM_NAMES, can_manage


def build_result_embed(match_id: int, before=None, after=None) -> discord.Embed:
    match = db.get_match(match_id)
    players = db.get_match_players(match_id)
    final = match["status"] == "confirmed"
    winner = match["winner_team"]

    embed = discord.Embed(
        title=f"{'🏆 내전 결과' if final else '📝 내전 결과 입력'} #{match_id}",
        description=f"승리 팀: {TEAM_NAMES[winner] if winner else '미선택'}",
        color=0x57F287 if final else 0xFEE75C)
    for team in ("blue", "red"):
        lines = []
        for mp in (p for p in players if p["team"] == team):
            kda = f"{mp['kills']}/{mp['deaths']}/{mp['assists']}" if mp["kills"] is not None else "미입력"
            line = f"**{mp['lane']}** <@{mp['user_id']}> · {kda}"
            if mp["edited_by"] and mp["edited_by"] != mp["user_id"]:
                line += f" ✏️<@{mp['edited_by']}>"
            if before and after:
                b, a = before[mp["user_id"]], after[mp["user_id"]]
                line += f" · 전력 {b:.1f}→{a:.1f} ({a - b:+.1f})"
            lines.append(line)
        label = TEAM_NAMES[team] + (" (승)" if winner == team else "")
        embed.add_field(name=label, value="\n".join(lines), inline=False)
    if not final:
        embed.set_footer(text="이름 버튼을 눌러 KDA 입력 (누구나 누구 것이든 가능, ✏️=입력한 사람) · 확정은 방장만")
    return embed


class KdaModal(discord.ui.Modal):
    def __init__(self, result_view: "ResultView", mp):
        super().__init__(title=f"{mp['name'][:20]} KDA 입력")
        self.result_view = result_view
        self.user_id = mp["user_id"]

        def field(label, value):
            return discord.ui.TextInput(
                label=label, placeholder="숫자", required=True, max_length=2,
                default=str(value) if value is not None else None)

        self.k = field("킬", mp["kills"])
        self.d = field("데스", mp["deaths"])
        self.a = field("어시스트", mp["assists"])
        for item in (self.k, self.d, self.a):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            k, d, a = int(self.k.value), int(self.d.value), int(self.a.value)
        except ValueError:
            await interaction.response.send_message("킬/데스/어시스트는 숫자로 입력해 주세요.", ephemeral=True)
            return
        if min(k, d, a) < 0:
            await interaction.response.send_message("음수는 입력할 수 없어요.", ephemeral=True)
            return
        if db.get_match(self.result_view.match_id)["status"] != "open":
            await interaction.response.send_message("이미 끝난 내전이에요.", ephemeral=True)
            return
        db.set_kda(self.result_view.match_id, self.user_id, k, d, a, interaction.user.id)
        await self.result_view.update(interaction)


class PlayerButton(discord.ui.Button):
    def __init__(self, result_view: "ResultView", mp):
        entered = mp["kills"] is not None
        super().__init__(
            label=f"{'✅' if entered else '⬜'} {mp['lane']} {mp['name'][:10]}",
            style=discord.ButtonStyle.primary if mp["team"] == "blue" else discord.ButtonStyle.danger,
            row=0 if mp["team"] == "blue" else 1)
        self.result_view = result_view
        self.mp = mp

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(KdaModal(self.result_view, self.mp))


class ResultView(discord.ui.View):
    def __init__(self, match_id: int):
        super().__init__(timeout=6 * 3600)
        self.match_id = match_id
        self._player_buttons = []
        self.sync()

    def sync(self):
        """DB 상태에 맞게 버튼 표시를 갱신"""
        for b in self._player_buttons:
            self.remove_item(b)
        self._player_buttons = []
        for mp in db.get_match_players(self.match_id):
            btn = PlayerButton(self, mp)
            self.add_item(btn)
            self._player_buttons.append(btn)
        winner = db.get_match(self.match_id)["winner_team"]
        self.blue_win.style = discord.ButtonStyle.success if winner == "blue" else discord.ButtonStyle.secondary
        self.red_win.style = discord.ButtonStyle.success if winner == "red" else discord.ButtonStyle.secondary

    async def update(self, interaction: discord.Interaction):
        self.sync()
        await interaction.response.edit_message(embed=build_result_embed(self.match_id), view=self)

    async def _set_winner(self, interaction: discord.Interaction, team: str):
        if db.get_match(self.match_id)["status"] != "open":
            await interaction.response.send_message("이미 끝난 내전이에요.", ephemeral=True)
            return
        db.set_winner(self.match_id, team)
        await self.update(interaction)

    @discord.ui.button(label="🔵 블루 승", style=discord.ButtonStyle.secondary, row=2)
    async def blue_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_winner(interaction, "blue")

    @discord.ui.button(label="🔴 레드 승", style=discord.ButtonStyle.secondary, row=2)
    async def red_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_winner(interaction, "red")

    @discord.ui.button(label="✅ 결과 확정", style=discord.ButtonStyle.success, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = db.get_match(self.match_id)
        if match["status"] != "open":
            await interaction.response.send_message("이미 끝난 내전이에요.", ephemeral=True)
            return
        if not can_manage(interaction, match["host_id"]):
            await interaction.response.send_message("방장(또는 서버 관리 권한)만 확정할 수 있어요.", ephemeral=True)
            return
        players = db.get_match_players(self.match_id)
        missing = [mp["name"] for mp in players if mp["kills"] is None]
        if match["winner_team"] is None or missing:
            problems = []
            if match["winner_team"] is None:
                problems.append("승리 팀을 선택해 주세요")
            if missing:
                problems.append("KDA 미입력: " + ", ".join(missing))
            await interaction.response.send_message("확정할 수 없어요.\n- " + "\n- ".join(problems), ephemeral=True)
            return

        before = {mp["user_id"]: analysis.user_power(mp["user_id"]) for mp in players}
        db.confirm_match(self.match_id)
        after = {mp["user_id"]: analysis.user_power(mp["user_id"]) for mp in players}
        self.stop()
        await interaction.response.edit_message(
            embed=build_result_embed(self.match_id, before, after), view=None)

    @discord.ui.button(label="🗑️ 내전 취소", style=discord.ButtonStyle.secondary, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = db.get_match(self.match_id)
        if not can_manage(interaction, match["host_id"]):
            await interaction.response.send_message("방장(또는 서버 관리 권한)만 취소할 수 있어요.", ephemeral=True)
            return
        db.cancel_match(self.match_id)
        self.stop()
        await interaction.response.edit_message(content="내전이 취소됐어요. (전적에 반영되지 않아요)", embed=None, view=None)
