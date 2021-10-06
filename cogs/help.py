from copy import deepcopy
from discord.ext import commands
from lib.embeds import *
from lib.prefixes import get_prefix

BASE_HELP_DICT = {
    KEY_TITLE: 'Help',
    KEY_DESCRIPTION: 'These are the currently available CirqueBot modules. Use the example commands below to get more '
                     'information about each one.',
    KEY_COMMAND: '!cb help',
    KEY_SUBCOMMANDS: []
}


class Help(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        if ctx.guild:
            await Help.show_help(self.bot, ctx.message)

    @staticmethod
    async def show_help(bot, message):
        help_cogs = []
        for cog_name, cog_object in bot.cogs.items():
            if hasattr(cog_object, 'help') and not callable(getattr(cog_object, 'help')):
                help_cogs.append((cog_name, cog_object))
        help_cogs.sort()
        help_dict = Help.build_help_dict(help_cogs)
        prefix = get_prefix(bot, message)
        await message.channel.send(embed=create_help_embed(help_dict, prefix))

    @staticmethod
    def build_help_dict(help_cogs: list):
        help_dict = deepcopy(BASE_HELP_DICT)
        for cog_name, cog_object in help_cogs:
            help_dict[KEY_SUBCOMMANDS].append({
                KEY_EMOJI: cog_object.help[KEY_EMOJI],
                KEY_TITLE: cog_object.help[KEY_TITLE],
                KEY_DESCRIPTION: cog_object.help[KEY_DESCRIPTION],
                KEY_EXAMPLE: cog_object.help[KEY_COMMAND]
            })
        return help_dict


def setup(bot):
    bot.add_cog(Help(bot))
