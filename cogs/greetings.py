from aiosqlite import connect
from asyncio import Lock, TimeoutError, sleep
from discord.ext import commands
from lib.embeds import *
from lib.prefixes import get_prefix
from lib.utils import log
from re import sub

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
CLEAR_STRING = '<clear>'

DELAY_SECONDS = 1  # How many seconds to wait after a user joins the server before sending the greeting message(s).
TIMEOUT_SECONDS = 180  # How many seconds to wait for a reaction/message before canceling the configuration session.

BLANK_CONFIG = {
    KEY_PUBLIC_CHANNEL_ID: 0,
    KEY_PUBLIC_MESSAGE: '',
    KEY_PRIVATE_MESSAGE: ''
}

CONFIG_MENU_EMOJI = [EMOJI_PUBLIC_CHANNEL, EMOJI_PUBLIC_MESSAGE, EMOJI_PRIVATE_MESSAGE, EMOJI_SUCCESS, EMOJI_ERROR]

CONFIG_MENU_TEXT = '\n\n**Configuration in progress! Please react with one of the following emoji:**' \
                   f'\n \u200B \u200B \u200B {EMOJI_PUBLIC_CHANNEL} = Edit public greeting channel' \
                   f'\n \u200B \u200B \u200B {EMOJI_PUBLIC_MESSAGE} = Edit public greeting message' \
                   f'\n \u200B \u200B \u200B {EMOJI_PRIVATE_MESSAGE} = Edit private greeting message' \
                   f'\n \u200B \u200B \u200B {EMOJI_SUCCESS} = Save and activate the current configuration' \
                   f'\n \u200B \u200B \u200B {EMOJI_ERROR} = Scrap the current session and discard all changes'

CONFIG_MESSAGE_TIPS = '\n\n**Some helpful tips:**' \
                      f'\n \u200B - You may use `{USER_STRING}` in your message to mention/ping the new member.' \
                      f'\n \u200B - You may use `{SERVER_STRING}` in your message to display this server\'s name.' \
                      f'\n \u200B - You may use Markdown formatting (e.g. `**bold text**`) in your message.' \
                      f'\n \u200B - You may type `{CLEAR_STRING}` to remove an existing greeting message.' \
                      '\n\n**Example:** \u200B `Hello <user>! Welcome to **<server>**! 😄`' \
                      '\n\nPlease type out and send your desired greeting message now.'

CONFIG_PROMPT_PUBLIC = '**What should I say in my public greeting message to new members?**' + CONFIG_MESSAGE_TIPS
CONFIG_PROMPT_PRIVATE = '**What should I say in my private greeting DM to new members?**' + CONFIG_MESSAGE_TIPS
CONFIG_PROMPT_CHANNEL = '**Which channel should be used for public greetings in this server?**' \
                        '\n\n**Example:** \u200B {0}\n\nPlease tag your desired channel now.'  # arg: channel_mention

CONFIG_TIMEOUT_TEXT = 'You\'re too slow! \u200B \u200B 🦥 \u200B Canceled the config session and reverted any changes.'


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
        self.cache = {}
        self.cache_lock = Lock()
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
        display_message = await ctx.send(embed=Greetings.get_display_embed(self.bot, ctx.guild, config))
        session_cog = Greetings.GTSession(self, ctx, config, display_message)
        self.bot.add_cog(session_cog)
        await session_cog.show_menu()

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
        async with self.cache_lock:
            if server.id in self.cache:
                return self.cache[server.id]
            config = BLANK_CONFIG.copy()
            async with connect(self.db) as connection:
                async with connection.execute('SELECT * FROM greetings WHERE server_id=?', (server.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        config[KEY_PUBLIC_CHANNEL_ID] = row[1]
                        config[KEY_PUBLIC_MESSAGE] = row[2]
                        config[KEY_PRIVATE_MESSAGE] = row[3]
            self.cache[server.id] = config
            return config

    async def save_config_for_server(self, server, config):
        async with self.cache_lock:
            self.cache[server.id] = config
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
        async with self.cache_lock:
            self.cache.pop(server.id, None)
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

    class GTSession(commands.Cog):
        def __init__(self, parent, ctx, config, display_message):
            self.parent = parent
            self.bot = parent.bot
            self.owner = ctx.author
            self.channel = ctx.channel
            self.server = ctx.guild
            self.config = config.copy()
            self.display_message = display_message
            self.messages_to_delete = set()

        def check_message(self, message):
            return (message.author.id == self.owner.id) and (message.channel.id == self.channel.id)

        def check_reaction(self, reaction, user):
            return (user.id == self.owner.id) and (str(reaction.emoji) in CONFIG_MENU_EMOJI)

        async def prompt_for_message(self, prompt_text, prompt_emoji, callback):
            prompt_message = await self.channel.send(embed=create_basic_embed(prompt_text, prompt_emoji))
            try:
                user_message = \
                    await self.bot.wait_for('message', timeout=TIMEOUT_SECONDS, check=self.check_message)
            except TimeoutError:
                self.messages_to_delete.update({prompt_message})
                await self.finish(create_basic_embed(CONFIG_TIMEOUT_TEXT, EMOJI_ERROR))
            else:
                await prompt_message.delete()
                await callback(user_message)

        async def show_menu(self):
            menu_message = await self.channel.send(embed=create_basic_embed(CONFIG_MENU_TEXT))
            for emoji in CONFIG_MENU_EMOJI:
                await menu_message.add_reaction(emoji)
            try:
                reaction, unused_user = \
                    await self.bot.wait_for('reaction_add', timeout=TIMEOUT_SECONDS, check=self.check_reaction)
            except TimeoutError:
                self.messages_to_delete.update({menu_message})
                await self.finish(create_basic_embed(CONFIG_TIMEOUT_TEXT, EMOJI_ERROR))
            else:
                await menu_message.delete()
                await self.handle_menu_option(str(reaction))

        async def handle_menu_option(self, emoji):
            if emoji == EMOJI_PUBLIC_CHANNEL:
                prompt_text = CONFIG_PROMPT_CHANNEL.format(self.channel.mention)
                await self.prompt_for_message(prompt_text, emoji, self.handle_public_channel_change)
            elif emoji == EMOJI_PUBLIC_MESSAGE:
                await self.prompt_for_message(CONFIG_PROMPT_PUBLIC, emoji, self.handle_public_message_change)
            elif emoji == EMOJI_PRIVATE_MESSAGE:
                await self.prompt_for_message(CONFIG_PROMPT_PRIVATE, emoji, self.handle_private_message_change)
            elif emoji == EMOJI_SUCCESS:
                await self.save_config_changes()
            elif emoji == EMOJI_ERROR:
                embed_text = 'Canceled the greeting configuration session and reverted any changes.'
                await self.finish(create_basic_embed(embed_text, emoji))

        async def handle_public_channel_change(self, user_message):
            if len(user_message.channel_mentions) == 1:
                public_channel = user_message.channel_mentions[0]
                bot_member = self.server.get_member(self.bot.user.id)
                if public_channel.permissions_for(bot_member).send_messages:
                    self.config[KEY_PUBLIC_CHANNEL_ID] = public_channel.id
                    display_embed = Greetings.get_display_embed(self.bot, self.server, self.config)
                    await self.display_message.edit(embed=display_embed)
                    success_embed_text = f'Public greeting messages will now be sent to {public_channel.mention}.'
                    await self.channel.send(embed=create_basic_embed(success_embed_text, EMOJI_SUCCESS))
                else:
                    embed_text = f'I don\'t have permission to post in {public_channel.mention}. No changes made.'
                    cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                    self.messages_to_delete.update({cancellation_message})
            else:
                embed_text = f'**"{user_message.content}"** did not specify exactly one channel. No changes made.'
                cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                self.messages_to_delete.update({cancellation_message})
            await user_message.delete()
            await self.show_menu()

        async def handle_public_message_change(self, user_message):
            await self.handle_message_change(user_message, KEY_PUBLIC_MESSAGE, 'public')

        async def handle_private_message_change(self, user_message):
            await self.handle_message_change(user_message, KEY_PRIVATE_MESSAGE, 'private')

        async def handle_message_change(self, user_message, config_key, identifier_string):
            original_message_text = user_message.content
            unformatted_message_text = sub('[*_~`|]', '', original_message_text).strip()
            if unformatted_message_text:
                # The user's message is guaranteed to contain something that isn't whitespace or formatting characters.
                if unformatted_message_text != CLEAR_STRING:
                    self.config[config_key] = sub('```', '', original_message_text).strip()
                    success_embed_text = f'The {identifier_string} greeting message has been updated!'
                else:
                    self.config[config_key] = BLANK_CONFIG[config_key]
                    success_embed_text = f'The {identifier_string} greeting message has been removed.'
                display_embed = Greetings.get_display_embed(self.bot, self.server, self.config)
                await self.display_message.edit(embed=display_embed)
                await self.channel.send(embed=create_basic_embed(success_embed_text, EMOJI_SUCCESS))
            else:
                embed_text = f'Invalid message content: `{original_message_text}`. No changes made.'
                cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                self.messages_to_delete.update({cancellation_message})
            await user_message.delete()
            await self.show_menu()

        async def save_config_changes(self):
            existing_config = await self.parent.get_config_for_server(self.server)
            if list(existing_config.values()) == list(self.config.values()):
                embed = create_basic_embed('Config session ended. You didn\'t make any changes!', '🤨')
            else:
                await self.parent.save_config_for_server(self.server, self.config)
                embed = create_basic_embed('Your config changes have been saved and are now live!', '🥳')
            await self.finish(embed)

        async def finish(self, embed):
            await self.channel.delete_messages(self.messages_to_delete)
            await self.channel.send(embed=embed)
            self.bot.remove_cog('GTSession')


def setup(bot):
    bot.add_cog(Greetings(bot))
