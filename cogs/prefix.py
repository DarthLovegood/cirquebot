import json
from discord.ext import commands
from lib.embeds import *
from lib.prefixes import *

# These format strings expect the following arguments in order: server_name, command_prefix
TEXT_DISPLAY_FORMAT = 'Command prefix in **{0}**: \u200B \u200B **`{1}`**'
TEXT_UPDATED_FORMAT = 'Command prefix in **{0}** updated! New prefix: \u200B \u200B **`{1}`**'


class Prefix(commands.Cog):
    help = {
        KEY_EMOJI: '🛠️',
        KEY_TITLE: 'Prefix',
        KEY_DESCRIPTION: 'Allows customization of the prefix used for this bot\'s commands.',
        KEY_COMMAND: '!cb prefix',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🔍',
                KEY_TITLE: 'show',
                KEY_DESCRIPTION: 'Displays the prefix currently used for commands in this server.',
                KEY_EXAMPLE: '!cb pf show'
            },
            {
                KEY_EMOJI: '🛠️',
                KEY_TITLE: 'set [prefix]',
                KEY_DESCRIPTION: 'Changes the prefix used for commands in this server to the given string.',
                KEY_EXAMPLE: '!cb pf set "!"'
            },
            {
                KEY_EMOJI: '🔄',
                KEY_TITLE: 'reset',
                KEY_DESCRIPTION: 'Resets the prefix used for commands in this server to the default `!cb\u200B `.',
                KEY_EXAMPLE: '!cb pf reset'
            }
        ]
    }

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['pf'])
    async def prefix(self, ctx, command: str = None, *args):
        if command == 'show' and not args:
            embed_text = TEXT_DISPLAY_FORMAT.format(ctx.guild.name, get_prefix(self.bot, ctx.message))
            await ctx.send(embed=create_basic_embed(embed_text, '🔍'))
        elif command == 'set' and len(args) == 1 and await Prefix.check_admin(ctx):
            await Prefix.set_prefix(ctx, args[0])
        elif command == 'reset' and not args and await Prefix.check_admin(ctx):
            await Prefix.set_prefix(ctx, DEFAULT_PREFIX)
        else:
            prefix = get_prefix(self.bot, ctx.message)
            await ctx.send(embed=create_help_embed(self.help, prefix))

    @staticmethod
    async def check_admin(ctx):
        is_admin = ctx.author.guild_permissions.administrator
        if not is_admin:
            await ctx.send(embed=create_basic_embed("Sorry, you aren't authorized to use that command!", EMOJI_ERROR))
        return is_admin

    @staticmethod
    async def set_prefix(ctx, new_prefix):
        with open(PREFIXES_PATH, 'r') as file:
            prefixes = json.load(file)

        server_id = str(ctx.guild.id)
        if (new_prefix == DEFAULT_PREFIX) and (server_id in prefixes):
            prefixes.pop(server_id)
        else:
            prefixes[server_id] = new_prefix

        with open(PREFIXES_PATH, 'w') as file:
            json.dump(prefixes, file, indent=4)

        embed_text = TEXT_UPDATED_FORMAT.format(ctx.guild.name, new_prefix)
        await ctx.send(embed=create_basic_embed(embed_text, EMOJI_SUCCESS))


def setup(bot):
    bot.add_cog(Prefix(bot))
