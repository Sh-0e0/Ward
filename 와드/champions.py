"""재미용 챔피언 추천 (와일드리프트에 있는 챔피언만, champions.json 기준)"""
import json
import os
import random

import discord

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "champions.json")


def load() -> dict:
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick(lane: str | None = None, count: int = 3, rng=None):
    data = load()
    pool = [c for c in data["champions"] if lane is None or lane in c["lanes"]]
    return (rng or random).sample(pool, min(count, len(pool)))


class ChampionView(discord.ui.View):
    def __init__(self, owner_id: int, lane: str | None, count: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.lane = lane
        self.count = count

    def build_embed(self) -> discord.Embed:
        data = load()
        picks = pick(self.lane, self.count)
        embed = discord.Embed(
            title=f"🎲 챔피언 추천 · {self.lane or '전체 라인'}",
            description="\n".join(f"{i + 1}. **{c['ko']}** ({'/'.join(c['lanes'])})" for i, c in enumerate(picks)),
            color=0xEB459E)
        embed.set_footer(text=f"재미로만 봐 주세요! 와일드리프트 챔피언 {len(data['champions'])}명 기준 (패치 {data['patch']})")
        return embed

    @discord.ui.button(label="🎲 다시 뽑기", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("명령어를 친 사람만 다시 뽑을 수 있어요. /챔피언추천 을 직접 써 보세요!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
