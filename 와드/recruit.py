"""내전 모집 -> 팀 추천 -> 내전 시작"""
import discord

import analysis
import balance
import db
from balance import LANES
from tiers import tier_label
from utils import can_manage

SIZE = 10
CROWD_LIMIT = 2  # 한 라인에 이미 이 인원 이상 있으면 참가 전에 한 번 더 확인


class ConfirmView(discord.ui.View):
    """'그래도 진행할까요?' 확인창 (본인에게만 보임)"""

    def __init__(self, on_yes):
        super().__init__(timeout=60)
        self._on_yes = on_yes

    @discord.ui.button(label="그래도 진행", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self._on_yes(interaction)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="취소했어요.", view=None)


class LaneSelectView(discord.ui.View):
    """참가 후 플레이 가능한 라인을 바꾸는 선택창 (본인에게만 보임)"""

    def __init__(self, recruit: "RecruitView", user_id: int):
        super().__init__(timeout=120)
        self.recruit = recruit
        self.user_id = user_id
        current = recruit.players.get(user_id, [])
        self.select = discord.ui.Select(
            placeholder="플레이 가능한 라인을 모두 골라 주세요",
            min_values=1, max_values=len(LANES),
            options=[discord.SelectOption(label=l, default=l in current) for l in LANES])
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        r = self.recruit
        if self.user_id not in r.players or r.closed:
            await interaction.response.edit_message(content="이미 모집이 끝났거나 참가 상태가 아니에요.", view=None)
            return
        main = db.get_user(self.user_id)["main_lane"]
        lanes = sorted(self.select.values, key=lambda l: (l != main, LANES.index(l)))

        async def apply(inter: discord.Interaction):
            if self.user_id not in r.players or r.closed:
                await inter.response.edit_message(content="이미 모집이 끝났거나 참가 상태가 아니에요.", view=None)
                return
            r.players[self.user_id] = lanes
            await inter.response.edit_message(content=f"라인을 {'/'.join(lanes)}(으)로 변경했어요.", view=None)
            await r.push_update()

        crowd = r.crowded(lanes[0], self.user_id)
        if lanes[0] != r.players[self.user_id][0] and len(crowd) >= CROWD_LIMIT:
            await interaction.response.edit_message(content=r.crowd_warning(lanes[0], crowd), view=ConfirmView(apply))
        else:
            await apply(interaction)


class RecruitView(discord.ui.View):
    def __init__(self, host_id: int, title: str):
        super().__init__(timeout=6 * 3600)
        self.host_id = host_id
        self.title = title
        self.players: dict[int, list[str]] = {}  # user_id -> 플레이 가능한 라인 (주 라인이 맨 앞)
        self.closed = False
        self.channel = None
        self.message_id = None

    # ----- 라인 중복 확인 -----
    def crowded(self, lane: str, exclude_uid: int) -> list[int]:
        """해당 라인을 주 라인으로 참가한 (본인 제외) 사람들"""
        return [uid for uid, lanes in self.players.items() if uid != exclude_uid and lanes[0] == lane]

    @staticmethod
    def crowd_warning(lane: str, crowd: list[int]) -> str:
        mentions = ", ".join(f"<@{u}>" for u in crowd)
        return (f"⚠️ **{lane}** 주 라인이 이미 {len(crowd)}명 있어요 ({mentions}).\n"
                f"한 팀에 {lane}은 1명이라서, 3명 이상이면 누군가는 다른 라인으로 배치될 수 있어요. 그래도 진행할까요?")

    def try_add(self, uid: int):
        """참가 처리. 실패하면 사유 문자열, 성공하면 None"""
        if self.closed:
            return "이미 모집이 끝났어요."
        user = db.get_user(uid)
        if user is None:
            return "먼저 /티어등록 으로 티어와 라인을 등록해 주세요."
        if uid in self.players:
            return "이미 참가했어요."
        if len(self.players) >= SIZE:
            return "이미 10명이 다 찼어요."
        self.players[uid] = [user["main_lane"]] + ([user["sub_lane"]] if user["sub_lane"] else [])
        return None

    # ----- 표시 -----
    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎮 {self.title}",
            description=f"방장: <@{self.host_id}>\n참가 **{len(self.players)}/{SIZE}**",
            color=0x57F287)
        if self.players:
            lines = []
            for uid, lanes in self.players.items():
                u = db.get_user(uid)
                lines.append(f"<@{uid}> · {tier_label(u['tier'], u['division'])} · {'/'.join(lanes)}")
            embed.add_field(name="참가자", value="\n".join(lines), inline=False)
        main_counts = {l: sum(1 for ls in self.players.values() if ls[0] == l) for l in LANES}
        embed.add_field(
            name="라인별 주 라인 인원 (⚠️ = 3명 이상)",
            value=" | ".join(f"{l} {n}{' ⚠️' if n > CROWD_LIMIT else ''}" for l, n in main_counts.items()),
            inline=False)
        if len(self.players) >= SIZE:
            embed.set_footer(text="10명이 모였어요! 방장이 '팀 짜기'를 눌러 주세요.")
        else:
            embed.set_footer(text="참가하려면 먼저 /티어등록 을 해야 해요.")
        return embed

    async def push_update(self):
        """버튼 클릭이 아닌 경로(라인 변경 등)에서 모집글을 갱신"""
        if self.closed or self.channel is None or self.message_id is None:
            return
        await self.channel.get_partial_message(self.message_id).edit(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        if self.closed:
            return
        self.closed = True
        try:
            await self.channel.get_partial_message(self.message_id).edit(
                content="⏰ 모집 시간이 지나 종료됐어요.", embed=None, view=None)
        except (discord.HTTPException, AttributeError):
            pass

    # ----- 버튼 -----
    async def confirm_join(self, interaction: discord.Interaction):
        err = self.try_add(interaction.user.id)
        if err:
            await interaction.response.edit_message(content=err, view=None)
            return
        await interaction.response.edit_message(
            content="참가했어요! 라인이 겹치니 '라인 변경'으로 다른 라인도 골라 두면 팀 배치가 쉬워져요.", view=None)
        await self.push_update()

    @discord.ui.button(label="참가", style=discord.ButtonStyle.success, row=0)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        user = db.get_user(uid)
        # 같은 주 라인이 이미 2명 이상이면 한 번 더 확인
        if user is not None and uid not in self.players and len(self.players) < SIZE and not self.closed:
            crowd = self.crowded(user["main_lane"], uid)
            if len(crowd) >= CROWD_LIMIT:
                await interaction.response.send_message(
                    self.crowd_warning(user["main_lane"], crowd),
                    view=ConfirmView(self.confirm_join), ephemeral=True)
                return
        err = self.try_add(uid)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, row=0)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.players.pop(interaction.user.id, None) is None:
            await interaction.response.send_message("참가 상태가 아니에요.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="라인 변경", style=discord.ButtonStyle.secondary, row=0)
    async def change_lane(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("먼저 참가 버튼을 눌러 주세요.", ephemeral=True)
            return
        await interaction.response.send_message(
            "팀 추천에 쓸 플레이 가능 라인을 골라 주세요.",
            view=LaneSelectView(self, interaction.user.id), ephemeral=True)

    @discord.ui.button(label="팀 짜기", style=discord.ButtonStyle.primary, row=1)
    async def make_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage(interaction, self.host_id):
            await interaction.response.send_message("방장만 누를 수 있어요.", ephemeral=True)
            return
        if len(self.players) != SIZE:
            await interaction.response.send_message(f"10명이 모여야 해요. (현재 {len(self.players)}명)", ephemeral=True)
            return
        players = [analysis.build_player(uid, lanes) for uid, lanes in self.players.items()]
        team_view = TeamView(self, balance.recommend(players))
        self.closed = True
        self.stop()
        await interaction.response.edit_message(embed=team_view.build_embed(), view=team_view)

    @discord.ui.button(label="모집 취소", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage(interaction, self.host_id):
            await interaction.response.send_message("방장만 누를 수 있어요.", ephemeral=True)
            return
        self.closed = True
        self.stop()
        await interaction.response.edit_message(content="모집이 취소됐어요.", embed=None, view=None)


class TeamView(discord.ui.View):
    def __init__(self, recruit: RecruitView, candidates):
        super().__init__(timeout=6 * 3600)
        self.recruit = recruit
        self.candidates = candidates
        self.idx = 0

    def build_embed(self) -> discord.Embed:
        return analysis.team_embed(self.candidates[self.idx], self.idx, len(self.candidates), self.recruit.title)

    @discord.ui.button(label="🔄 다시 뽑기", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage(interaction, self.recruit.host_id):
            await interaction.response.send_message("방장만 누를 수 있어요.", ephemeral=True)
            return
        self.idx = (self.idx + 1) % len(self.candidates)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✅ 이 팀으로 내전 시작", style=discord.ButtonStyle.success)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage(interaction, self.recruit.host_id):
            await interaction.response.send_message("방장만 누를 수 있어요.", ephemeral=True)
            return
        c = self.candidates[self.idx]
        rows = [(p.user_id, "blue", LANES[i]) for i, p in enumerate(c.blue)] + \
               [(p.user_id, "red", LANES[i]) for i, p in enumerate(c.red)]
        match_id = db.create_match(interaction.guild_id, self.recruit.host_id, self.recruit.title, rows)
        embed = analysis.team_embed(c, self.idx, len(self.candidates), self.recruit.title)
        embed.title = f"🏁 내전 시작 · {self.recruit.title}"
        embed.set_footer(text=f"내전 #{match_id} · 끝나면 /게임끝 으로 결과를 입력하세요.")
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
