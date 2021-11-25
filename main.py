import discord
import sys
from discord.ext import commands
from lib.prefixes import get_prefix
from secrets import BOT_TOKEN_DEV, BOT_TOKEN_LITE, BOT_TOKEN_PROD

CONFIG_LITE = 'LITE'
CONFIG_PROD = 'PROD'
CONFIG_DEV = 'DEV'

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=get_prefix, help_command=None, intents=intents)


def initialize_bot(config):
    # Extensions that should be loaded for all bot configurations.
    bot.load_extension('cogs.help')
    bot.load_extension('cogs.prefix')
    bot.load_extension('cogs.reactions')

    if config == CONFIG_LITE:
        return BOT_TOKEN_LITE

    # Extensions that should only be loaded for PROD and DEV configurations.
    bot.load_extension('cogs.audio_player')
    bot.load_extension('cogs.easter_eggs')
    bot.load_extension('cogs.greetings')
    bot.load_extension('cogs.nicknames')
    bot.load_extension('cogs.rewrite')
    bot.load_extension('cogs.sniper')

    if config == CONFIG_PROD:
        return BOT_TOKEN_PROD

    # Extensions that should only be loaded for DEV configuration.
    bot.load_extension('cogs.clownquest')
    bot.load_extension('cogs.events')

    return BOT_TOKEN_DEV


@bot.event
async def on_ready():
    print(f'Successfully logged in as: {bot.user}')
    await bot.change_presence(activity=discord.Game(name='!cb help'))


if __name__ == '__main__':
    config_arg = '' if len(sys.argv) != 2 else sys.argv[1].upper()
    config_option = config_arg if config_arg in [CONFIG_LITE, CONFIG_PROD, CONFIG_DEV] else CONFIG_PROD
    bot_token = initialize_bot(config_option)
    print(f'[Configuration: {config_option}] Logging in...')
    bot.run(bot_token)
