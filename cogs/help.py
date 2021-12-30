from cogs.permissions import Permissions
from copy import deepcopy
from discord import Message
from discord.ext.commands import Bot, Cog, Context, command
from lib.embeds import *
from lib.permission import Permission
from lib.prefixes import get_prefix

BASE_HELP_DICT = {
    KEY_TITLE: 'Help',
    KEY_DESCRIPTION: 'These are the currently available CirqueBot modules. Use the example commands below to get more '
                     'information about each one.',
    KEY_COMMAND: '!cb help',
    KEY_SUBCOMMANDS: []
}


class Help(Cog):

    def __init__(self, bot: Bot):
        self.bot = bot

    @command()
    async def help(self, ctx: Context):
        await Help.show_help(self.bot, ctx.message)

    @staticmethod
    async def show_help(bot: Bot, message: Message):
        if not await Permissions.check(bot, Permission.VIEW_HELP, message.guild, message.channel):
            await message.channel.send(embed=create_error_embed(TEXT_MISSING_PERMISSION))
            return

        help_cogs = []
        for cog_name, cog_object in bot.cogs.items():
            if hasattr(cog_object, 'help') and not callable(getattr(cog_object, 'help')):
                help_cogs.append((cog_name, cog_object))
        help_cogs.sort()

        await message.channel.send(embed=create_help_embed(Help.build_help_dict(help_cogs), get_prefix(bot, message)))

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


def setup(bot: Bot):
    bot.add_cog(Help(bot))
