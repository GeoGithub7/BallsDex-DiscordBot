import discord
import logging

from typing import Optional
from tortoise.exceptions import DoesNotExist
from discord.ext import commands
from discord.utils import format_dt

from ballsdex.core.models import GuildConfig, Ball
from ballsdex.packages.countryballs.spawn import SpawnManager
from ballsdex.packages.countryballs.countryball import CountryBall

log = logging.getLogger("ballsdex.packages.countryballs")


class CountryBallsSpawner(commands.Cog):
    def __init__(self):
        self.spawn_manager = SpawnManager()

    async def load_cache(self):
        i = 0
        async for config in GuildConfig.all():
            if not config.enabled:
                continue
            if not config.spawn_channel:
                continue
            self.spawn_manager.cache[config.guild_id] = config.spawn_channel
            i += 1
        log.info(f"Loaded {i} guilds in cache")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        guild = message.guild
        if not guild:
            return
        if guild.id not in self.spawn_manager.cache:
            return
        await self.spawn_manager.handle_message(message)

    @commands.Cog.listener()
    async def on_ballsdex_settings_change(
        self,
        guild: discord.Guild,
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None,
    ):
        if guild.id not in self.spawn_manager.cache:
            if enabled is False:
                return  # do nothing
            if channel:
                self.spawn_manager.cache[guild.id] = channel.id
            else:
                try:
                    config = await GuildConfig.get(guild_id=guild.id)
                except DoesNotExist:
                    return
                else:
                    self.spawn_manager.cache[guild.id] = config.spawn_channel
        else:
            if enabled is False:
                del self.spawn_manager.cache[guild.id]
            elif channel:
                self.spawn_manager.cache[guild.id] = channel.id

    @commands.command()
    @commands.is_owner()
    async def spawnball(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        *,
        ball: str | None = None,
    ):
        """
        Force spawn a countryball.
        """
        if not ball:
            countryball = await CountryBall.get_random()
        else:
            try:
                ball_model = await Ball.get(country__iexact=ball.lower())
            except DoesNotExist:
                await ctx.send("No such ball exists.")
                return
            countryball = CountryBall(ball_model)
        await countryball.spawn(channel or ctx.channel)

    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def spawnstats(self, ctx: commands.Context):
        """
        Get details about countryball spawner.
        """
        assert ctx.guild
        if ctx.guild.id not in self.spawn_manager.cache:
            await ctx.send("That guild does not have a registered spawn channel.")
            return
        cooldown_manager = self.spawn_manager.cooldowns[ctx.guild.id]
        await ctx.send(
            f"Initiated {format_dt(cooldown_manager.time, style='R')}\n"
            f"Counter: {cooldown_manager.amount}/{cooldown_manager.chance}"
        )
