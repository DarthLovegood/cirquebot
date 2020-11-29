import discord

from discord.ext import commands
from secrets import BOT_TOKEN


COMMAND_PREFIX = '!cb '

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f'Successfully logged in as: {bot.user}')
    bot.load_extension('cogs.clownquest')
    # bot.load_extension('cogs.events')
    bot.load_extension('cogs.nicknames')
    # bot.load_extension('cogs.welcome')


if __name__ == '__main__':
    print('Logging in...')
    bot.run(BOT_TOKEN)
