from aiosqlite import connect
from asyncio import sleep
from discord.ext import commands
from lib.embeds import *
from lib.prefixes import get_prefix
from lib.utils import log

KEY_PUBLIC_CHANNEL_ID = 'public_channel_id'
KEY_PUBLIC_MESSAGE = 'public_message'
KEY_PRIVATE_MESSAGE = 'private_message'

EMOJI_PUBLIC_CHANNEL = '📡'
EMOJI_PUBLIC_MESSAGE = '📢'
EMOJI_PRIVATE_MESSAGE = '📨'

TEXT_GREETING_EMPTY = '\n```diff\n- NONE -```'
TEXT_GREETING_MESSAGE = '\n```xml\n{0}```'  # arg: message_text
TEXT_GREETING_ACTIVE = '**active**'
TEXT_GREETING_INACTIVE = '**inactive**'
TEXT_GREETING_SUMMARY = '\nCurrently, the public greeting is {0} and the private greeting is {1}.' \
                        '\nYou may activate (or deactivate) one or both of these greetings at any time.\n'
TEXT_GREETING_NONE = '**{0}** is not currently configured to send any greetings.'  # arg: server_name

USER_STRING = '<user>'
SERVER_STRING = '<server>'

DELAY_SECONDS = 1  # How many seconds to wait after a user joins the server before sending the greeting message(s).

BLANK_CONFIG = {
    KEY_PUBLIC_CHANNEL_ID: 0,
    KEY_PUBLIC_MESSAGE: '',
    KEY_PRIVATE_MESSAGE: ''
}


class Greetings(commands.Cog):
    db = 'data/greetings.db'
    help = {
        KEY_EMOJI: '👋',
        KEY_TITLE: 'Greetings',
        KEY_DESCRIPTION: 'Manages the automatic messages to be sent when a new member joins this server.',
        KEY_COMMAND: '!cb greetings',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🛠️',
                KEY_TITLE: 'config',
                KEY_DESCRIPTION: 'Starts a session to edit the greeting configuration for this server.',
                KEY_EXAMPLE: '!cb gt config'
            },
            {
                KEY_EMOJI: '🧐',
                KEY_TITLE: 'demo',
                KEY_DESCRIPTION: 'Demonstrates the greeting(s) that will be sent when someone joins this server.',
                KEY_EXAMPLE: '!cb gt demo'
            },
            {
                KEY_EMOJI: '🧼',
                KEY_TITLE: 'reset',
                KEY_DESCRIPTION: 'Wipes the greeting configuration for this server.',
                KEY_EXAMPLE: '!cb gt reset'
            }
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_database())

    async def initialize_database(self):
        async with connect(self.db) as connection:
            cursor = await connection.execute(
                '''CREATE TABLE IF NOT EXISTS `greetings` (
                    `server_id` INTEGER PRIMARY KEY UNIQUE,
                    `public_channel_id` INTEGER,
                    `public_message` TEXT NOT NULL,
                    `private_message` TEXT NOT NULL
                );''')
            await connection.commit()
            await cursor.close()

    @commands.command(aliases=['greet', 'gt'])
    async def greetings(self, ctx, command: str = None, *args):
        if (len(args) != 0) or (command not in ['config', 'demo', 'reset']):
            prefix = get_prefix(self.bot, ctx.message)
            await ctx.send(embed=create_help_embed(self.help, prefix))
        elif command == 'config':
            await self.config(ctx)
        elif command == 'demo':
            await self.demo(ctx)
        elif command == 'reset':
            await self.reset(ctx)

    # Requires intents.members in order to work.
    @commands.Cog.listener()
    async def on_member_join(self, member):
        server = member.guild
        config = await self.get_config_for_server(server)
        log(f'GREETINGS: {member.name}#{member.discriminator} joined server "{server.name}".')
        await sleep(DELAY_SECONDS)  # Without this, the message might be sent before the user gets access to the server.

        if config[KEY_PUBLIC_MESSAGE] and config[KEY_PUBLIC_CHANNEL_ID]:
            channel = self.bot.get_channel(config[KEY_PUBLIC_CHANNEL_ID])
            bot_member = server.get_member(self.bot.user.id)
            if not channel:
                log(f'ERROR: Channel ID {config[KEY_PUBLIC_CHANNEL_ID]} is invalid. '
                    f'Could not post public greeting for {member.name}#{member.discriminator}.', indent=1)
            elif not channel.permissions_for(bot_member).send_messages:
                log(f'ERROR: Missing permission to send messages in channel "{channel.name}". '
                    f'Could not post public greeting for {member.name}#{member.discriminator}.', indent=1)
            else:
                message = Greetings.format_greeting_message(config[KEY_PUBLIC_MESSAGE], member, server)
                log(f'Posting public greeting for {member.name}#{member.discriminator} in "{channel.name}".', indent=1)
                await channel.send(message)
        else:
            log(f'Public greetings are currently disabled for "{server.name}"', indent=1)

        if config[KEY_PRIVATE_MESSAGE]:
            message = Greetings.format_greeting_message(config[KEY_PRIVATE_MESSAGE], member, server)
            log(f'Sending private greeting to {member.name}#{member.discriminator}.', indent=1)
            await member.send(message)
        else:
            log(f'Private greetings are currently disabled for "{server.name}"', indent=1)

    async def config(self, ctx):
        config = await self.get_config_for_server(ctx.guild)
        embed = Greetings.get_display_embed(self.bot, ctx.guild, config)
        await ctx.send(embed=embed)
        # TODO: Implement sessions to allow changing the server's configuration.

    async def demo(self, ctx):
        config = await self.get_config_for_server(ctx.guild)
        greeting_sent = False

        if config[KEY_PUBLIC_MESSAGE] and config[KEY_PUBLIC_CHANNEL_ID]:
            if config[KEY_PUBLIC_CHANNEL_ID] == ctx.channel.id:
                embed = None
            else:
                public_channel = self.bot.get_channel(config[KEY_PUBLIC_CHANNEL_ID])
                bot_member = ctx.guild.get_member(self.bot.user.id)
                if not public_channel:
                    comm = f'\u200B `{get_prefix(self.bot, ctx.message)}gt config` \u200B'
                    embed = create_basic_embed(f'Please re-run {comm} to select a valid greeting channel.', EMOJI_ERROR)
                elif not public_channel.permissions_for(bot_member).send_messages:
                    embed = create_basic_embed(f'The above message should be sent to the {public_channel.mention} '
                                               f'channel, but I don\'t have permission to post in there!', EMOJI_ERROR)
                else:
                    embed = create_basic_embed(f'The above message will be sent to {public_channel.mention} '
                                               f'(without this note, and with the correct user tagged if applicable) '
                                               f'when a new member joins this server.', EMOJI_SUCCESS)
            message = Greetings.format_greeting_message(config[KEY_PUBLIC_MESSAGE], ctx.author, ctx.guild)
            await ctx.send(message, embed=embed)
            greeting_sent = True

        if config[KEY_PRIVATE_MESSAGE]:
            message = Greetings.format_greeting_message(config[KEY_PRIVATE_MESSAGE], ctx.author, ctx.guild)
            await ctx.author.send(message)
            greeting_sent = True

        if not greeting_sent:
            await ctx.send(embed=create_basic_embed(TEXT_GREETING_NONE.format(ctx.guild.name), EMOJI_WARNING))

    async def reset(self, ctx):
        config_deleted = await self.delete_config_for_server(ctx.guild)
        if config_deleted:
            embed = create_basic_embed(f'Deleted greeting configuration for **{ctx.guild.name}**.', EMOJI_SUCCESS)
        else:
            embed = create_basic_embed(TEXT_GREETING_NONE.format(ctx.guild.name), EMOJI_WARNING)
        await ctx.send(embed=embed)

    # Always returns a valid (but maybe blank) config.
    async def get_config_for_server(self, server):
        config = BLANK_CONFIG.copy()
        async with connect(self.db) as connection:
            async with connection.execute('SELECT * FROM greetings WHERE server_id=?', (server.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    config[KEY_PUBLIC_CHANNEL_ID] = row[1]
                    config[KEY_PUBLIC_MESSAGE] = row[2]
                    config[KEY_PRIVATE_MESSAGE] = row[3]
        return config

    async def save_config_for_server(self, server, config):
        async with connect(self.db) as connection:
            async with connection.execute('SELECT * FROM greetings WHERE server_id=?', (server.id,)) as cursor:
                if await cursor.fetchone():
                    await cursor.execute('UPDATE greetings '
                                         'SET public_channel_id=?,'
                                         '    public_message=?,'
                                         '    private_message=? '
                                         'WHERE server_id=?',
                                         (config[KEY_PUBLIC_CHANNEL_ID],
                                          config[KEY_PUBLIC_MESSAGE],
                                          config[KEY_PRIVATE_MESSAGE],
                                          server.id))
                else:
                    await cursor.execute('INSERT INTO greetings VALUES (?, ?, ?, ?)',
                                         (server.id,
                                          config[KEY_PUBLIC_CHANNEL_ID],
                                          config[KEY_PUBLIC_MESSAGE],
                                          config[KEY_PRIVATE_MESSAGE]))
            await connection.commit()

    async def delete_config_for_server(self, server):
        config_deleted = False
        async with connect(self.db) as connection:
            async with connection.execute('SELECT * FROM greetings WHERE server_id=?', (server.id,)) as cursor:
                if await cursor.fetchone():
                    await cursor.execute('DELETE FROM greetings WHERE server_id=?', (server.id,))
                    config_deleted = True
            await connection.commit()
        return config_deleted

    @staticmethod
    def format_greeting_message(greeting_message, user, server):
        return greeting_message.replace(USER_STRING, user.mention).replace(SERVER_STRING, server.name)

    @staticmethod
    def get_display_embed(bot, server, config):
        title = f'Greeting Configuration for "{server.name}"'
        public_greeting_status = TEXT_GREETING_INACTIVE
        private_greeting_status = TEXT_GREETING_INACTIVE

        description = f'** **\n{EMOJI_PUBLIC_MESSAGE} \u200B **PUBLIC GREETING**\n'
        if config[KEY_PUBLIC_MESSAGE] and config[KEY_PUBLIC_CHANNEL_ID]:
            public_channel = bot.get_channel(config[KEY_PUBLIC_CHANNEL_ID])
            description += f'✅ \u200B This message will be sent to {public_channel.mention} when a new member joins.'
            description += TEXT_GREETING_MESSAGE.format(config[KEY_PUBLIC_MESSAGE])
            public_greeting_status = TEXT_GREETING_ACTIVE
        elif config[KEY_PUBLIC_MESSAGE]:
            description += '⚠️ \u200B Select a public channel to welcome new server members with this message.'
            description += TEXT_GREETING_MESSAGE.format(config[KEY_PUBLIC_MESSAGE])
        elif config[KEY_PUBLIC_CHANNEL_ID]:
            public_channel = bot.get_channel(config[KEY_PUBLIC_CHANNEL_ID])
            description += f'❔ \u200B Set a public message to welcome new server members in {public_channel.mention}.'
            description += TEXT_GREETING_EMPTY
        else:
            description += '❔ \u200B Set a public message to welcome new server members via a text channel.'
            description += TEXT_GREETING_EMPTY

        description += f'** **\n{EMOJI_PRIVATE_MESSAGE} \u200B **PRIVATE GREETING**\n'
        if config[KEY_PRIVATE_MESSAGE]:
            description += '✅ \u200B This message will be sent to new server members via DM.'
            description += TEXT_GREETING_MESSAGE.format(config[KEY_PRIVATE_MESSAGE])
            private_greeting_status = TEXT_GREETING_ACTIVE
        else:
            description += '❔ \u200B Set a private message to welcome new server members via DM.'
            description += TEXT_GREETING_EMPTY

        description = TEXT_GREETING_SUMMARY.format(public_greeting_status, private_greeting_status) + description
        return create_icon_embed(server.icon_url, title, description)


def setup(bot):
    bot.add_cog(Greetings(bot))
