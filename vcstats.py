# cogs/vcstats.py
import discord
from discord.ext import commands, tasks
import json
import os

STATS_PATH = r #replace this with where you want your stats to be stored in json

def load_stats(guild_id: int):
    path = os.path.join(STATS_PATH, f"{guild_id}.json")
    if not os.path.exists(path):
        return {"category_id": None, "stats": {}}
    with open(path, "r") as f:
        return json.load(f)

def save_stats(guild_id: int, data: dict):
    path = os.path.join(STATS_PATH, f"{guild_id}.json")
    os.makedirs(STATS_PATH, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

class VCStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stats.start()
        self.check_category.start()

    def cog_unload(self):
        self.update_stats.cancel()
        self.check_category.cancel()

    async def create_channel(self, guild, category, name):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False)  # deny joining
        }
        return await guild.create_voice_channel(name=name.lower(), category=category, overwrites=overwrites)

    async def update_channel(self, channel, name):
        new_name = name.lower()
        if channel and channel.name != new_name:
            await channel.edit(name=new_name)

    def get_stat_value(self, guild, stat):
        if stat == "members":
            return f"members: {sum(1 for m in guild.members if not m.bot)}"
        elif stat == "bots":
            return f"bots: {sum(1 for m in guild.members if m.bot)}"
        elif stat == "boosts":
            return f"boosts: {guild.premium_subscription_count}"
        elif stat == "boosters":
            return f"boosters: {len([m for m in guild.members if m.premium_since])}"
        elif stat == "total-messages":
            # placeholder – needs a message counter system
            return "total messages: 0"
        return f"{stat}: n/a"

    @commands.group(invoke_without_command=True)
    async def stats(self, ctx):
        await ctx.reply("usage: ,stats setup | ,stats add <stat> | ,stats remove <stat>")

    @stats.command()
    async def setup(self, ctx):
        guild = ctx.guild
        data = load_stats(guild.id)

        # if category id exists, verify it still exists in guild
        if data["category_id"]:
            category = guild.get_channel(data["category_id"])
            if category:
                return await ctx.reply("stats are already set up")
            else:
                # reset since category was deleted
                data = {"category_id": None, "stats": {}}
                save_stats(guild.id, data)

        # create category at top
        category = await guild.create_category_channel("server stats", position=0)
        data["category_id"] = category.id

        # default stats
        members_channel = await self.create_channel(guild, category, f"members: {sum(1 for m in guild.members if not m.bot)}")
        bots_channel = await self.create_channel(guild, category, f"bots: {sum(1 for m in guild.members if m.bot)}")

        data["stats"] = {
            "members": members_channel.id,
            "bots": bots_channel.id
        }

        save_stats(guild.id, data)
        await ctx.reply("stats setup completed")

    @stats.command()
    async def add(self, ctx, stat: str):
        guild = ctx.guild
        data = load_stats(guild.id)

        if not data["category_id"]:
            return await ctx.reply("please run ,stats setup first")

        if stat in data["stats"]:
            return await ctx.reply("that stat already exists")

        category = guild.get_channel(data["category_id"])
        if not category:
            return await ctx.reply("could not find stats category, try ,stats setup again")

        value = self.get_stat_value(guild, stat)
        channel = await self.create_channel(guild, category, value)
        data["stats"][stat] = channel.id
        save_stats(guild.id, data)

        await ctx.reply(f"added stat {stat}")

    @stats.command()
    async def remove(self, ctx, stat: str):
        guild = ctx.guild
        data = load_stats(guild.id)

        if stat not in data["stats"]:
            return await ctx.reply("that stat doesn’t exist")

        channel = guild.get_channel(data["stats"][stat])
        if channel:
            await channel.delete()

        del data["stats"][stat]
        save_stats(guild.id, data)

        await ctx.reply(f"removed stat {stat}")

    @tasks.loop(minutes=1)
    async def update_stats(self):
        for guild in self.bot.guilds:
            data = load_stats(guild.id)
            if not data["category_id"]:
                continue

            category = guild.get_channel(data["category_id"])
            if not category:
                continue

            for stat, channel_id in list(data["stats"].items()):
                channel = guild.get_channel(channel_id)
                if not channel:
                    continue
                value = self.get_stat_value(guild, stat)
                await self.update_channel(channel, value)

    @tasks.loop(seconds=10)  # check every 10s
    async def check_category(self):
        for guild in self.bot.guilds:
            data = load_stats(guild.id)
            if not data["category_id"]:
                continue

            category = guild.get_channel(data["category_id"])
            if not category:  # if category is gone, reset data
                save_stats(guild.id, {"category_id": None, "stats": {}})

async def setup(bot):
    await bot.add_cog(VCStats(bot))
