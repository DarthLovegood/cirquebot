import asyncio

from discord.ext import commands

MESSAGE_DELAY_SECONDS = 1
MESSAGE_TEXT = 'Welcome to the Cirque, {0.mention}! Please wait while an admin sets you up with the proper role to ' \
               'view our server. '


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Requires intents.members in order to work.
    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel is not None:
            await asyncio.sleep(MESSAGE_DELAY_SECONDS)
            await channel.send(MESSAGE_TEXT.format(member))


def setup(bot):
    bot.add_cog(Welcome(bot))
