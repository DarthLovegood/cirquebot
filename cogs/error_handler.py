from discord.ext import commands
from lib.embeds import create_basic_embed, EMOJI_ERROR

ERROR_BASIC_FORMAT = '**ERROR:** \u200B \u200B **`{0}`**'  # args: error


class ErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        await ctx.send(embed=create_basic_embed(ERROR_BASIC_FORMAT.format(error), EMOJI_ERROR))


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
