import asyncio
import json
import sqlite3
from datetime import datetime
from discord import HTTPException
from discord.ext import commands
from lib.embeds import *
from lib.prefixes import get_prefix
from lib.utils import log, extract_message_id, fetch_message
from secrets import SUPER_USERS

CONFIRMATION_TYPE_NONE = 0
CONFIRMATION_TYPE_PRIVATE = 1
CONFIRMATION_TYPE_PUBLIC = 2

KEY_MESSAGE_LINK = 'message_link'
KEY_IS_REACTIVE = 'is_reactive'
KEY_ALLOW_MULTISELECT = 'allow_multiselect'
KEY_ALLOW_CANCELLATION = 'allow_cancellation'
KEY_CONFIRMATION_TYPE = 'confirmation_type'
KEY_CONFIRMATION_CHANNEL_ID = 'confirmation_channel_id'
KEY_REACTION_ROLE_MENU = 'reaction_role_menu'

EMOJI_EDIT_MESSAGE_OPTIONS = '🛠️'
EMOJI_EDIT_REACTION_ROLES = '🏷️'
EMOJI_EDIT_CHANNEL = '📡'

EMOJI_ROLE_EDIT = '📝'
EMOJI_ROLE_DELETE = '🧼'

EMOJI_OPTION_REACTIVE_TRUE = '🎉'
EMOJI_OPTION_REACTIVE_FALSE = '🕵️'
EMOJI_OPTION_SELECT_MULTIPLE = '🤹'
EMOJI_OPTION_SELECT_SINGLE = '☝️'
EMOJI_OPTION_CANCELLABLE_TRUE = '👼'
EMOJI_OPTION_CANCELLABLE_FALSE = '👮'
EMOJI_OPTION_CONFIRMATION_NONE = '🔕'
EMOJI_OPTION_CONFIRMATION_PRIVATE = '📨'
EMOJI_OPTION_CONFIRMATION_PUBLIC = '📢'

EMOJI_OPTIONS = {
    KEY_IS_REACTIVE: [EMOJI_OPTION_REACTIVE_FALSE, EMOJI_OPTION_REACTIVE_TRUE],
    KEY_ALLOW_MULTISELECT: [EMOJI_OPTION_SELECT_SINGLE, EMOJI_OPTION_SELECT_MULTIPLE],
    KEY_ALLOW_CANCELLATION: [EMOJI_OPTION_CANCELLABLE_FALSE, EMOJI_OPTION_CANCELLABLE_TRUE],
    KEY_CONFIRMATION_TYPE:
        [EMOJI_OPTION_CONFIRMATION_NONE, EMOJI_OPTION_CONFIRMATION_PRIVATE, EMOJI_OPTION_CONFIRMATION_PUBLIC]
}

# These format strings expect the following arguments in order: role_name, emoji, message_link
TEXT_ALREADY_REACTED_FORMAT = '🤔 \u200B \u200B You already have the **{0}** role. Remove your \u200B {1} ' \
                              '\u200B reaction from [this message]({2}) if you don\'t want this role.'
TEXT_ALREADY_UNREACTED_FORMAT = '🤔 \u200B \u200B You don\'t currently have the **{0}** role. Add a \u200B {1} ' \
                                '\u200B reaction to [this message]({2}) if you would like this role.'

# These format strings expect the following arguments in order: emoji, role_name, message_link
TEXT_CONFIRMATION_PRIVATE_FORMAT = '{0} \u200B \u200B ' \
                                   'You have gained the **{1}** role by reacting to [this message]({2})!'
TEXT_CANCELLATION_PRIVATE_FORMAT = '{0} \u200B \u200B ' \
                                   'You have lost the **{1}** role by un-reacting to [this message]({2}).'

# These format strings expect the following arguments in order: emoji, user_mention, role_mention, message_link
TEXT_CONFIRMATION_PUBLIC_FORMAT = '{0} \u200B \u200B {1} has gained the {2} role from [this message]({3})!'
TEXT_CANCELLATION_PUBLIC_FORMAT = '{0} \u200B \u200B {1} has lost the {2} role from [this message]({3}).'

# These format strings expect the following argument: role_name
TEXT_CANCELLATIONS_DISABLED_FORMAT = '😢 \u200B \u200B Automatic removal is disabled for the **{0}** role. ' \
                                     'Please let an admin know if you would like this role to be removed.'
TEXT_REDUNDANT_REACTION_FORMAT = '🤔 \u200B \u200B You already have the **{0}** role. ' \
                                 'Please let an admin know if you would like this role to be removed.'

# This format string expects the following arguments in order: message_link, role name
TEXT_ALREADY_SELECTED_FORMAT = '☝️ \u200B \u200B You may only select one role from [this message]({0}), ' \
                               'and automatic switching is disabled. Please let an admin know if you would ' \
                               'like to change your selection (currently **{1}**).'

TEXT_REACTION_ROLE_MENU = f'\n \u200B \u200B \u200B {EMOJI_ROLE_EDIT} = Assign a different role to this reaction' \
                          f'\n \u200B \u200B \u200B {EMOJI_ROLE_DELETE} = Delete this reaction/role association' \
                          f'\n \u200B \u200B \u200B {EMOJI_ERROR} = Never mind, leave this reaction/role as is'
TEXT_MAIN_MENU = '\n\n**Configuration in progress! Please react with one of the following emoji:**' \
                 f'\n \u200B \u200B \u200B {EMOJI_EDIT_MESSAGE_OPTIONS} = Edit the options for the given message' \
                 f'\n \u200B \u200B \u200B {EMOJI_EDIT_REACTION_ROLES} = Edit or add reaction/role assignments' \
                 f'\n \u200B \u200B \u200B {EMOJI_EDIT_CHANNEL} = Edit public confirmation channel (if applicable)' \
                 f'\n \u200B \u200B \u200B {EMOJI_SUCCESS} = Save and activate the current configuration' \
                 f'\n \u200B \u200B \u200B {EMOJI_ERROR} = Scrap the current session and discard all changes'

TEXT_SESSION_TIMEOUT = 'You\'re too slow! \u200B \u200B 🦥 \u200B Canceled the config session and reverted any changes.'
SESSION_TIMEOUT_SECONDS = 180  # 3 minutes

REACTION_ADD = 'reaction_add'
REACTION_REMOVE = 'reaction_remove'

DATA_KEY_MESSAGE_ID = 'message_id'
DATA_KEY_CHANNEL_ID = 'channel_id'
DATA_KEY_REACTION_ROLES = 'reaction_roles'

CACHE_KEY_DATA = 'data'
CACHE_KEY_TIMESTAMP = 'timestamp'
CACHE_TTL_SECONDS = 3600  # 1 hour


class Reactions(commands.Cog):
    db = 'data/reactions.db'
    help = {
        KEY_TITLE: 'Reactions',
        KEY_DESCRIPTION: 'Manages the connections between message reactions and role assignments.',
        KEY_COMMAND: '!cb reactions',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🧾',
                KEY_TITLE: 'list',
                KEY_DESCRIPTION: 'Lists all of the messages on this server that have reaction/role configurations.',
                KEY_EXAMPLE: '!cb ra list'
            },
            {
                KEY_EMOJI: '🛠️',
                KEY_TITLE: 'config [message link]',
                KEY_DESCRIPTION: 'Starts a session to edit the reaction/role configuration for the linked message.',
                KEY_EXAMPLE: '!cb ra config https://discord.com/URL'
            },
            {
                KEY_EMOJI: '🧼',
                KEY_TITLE: 'reset [message link]',
                KEY_DESCRIPTION: 'Wipes the reaction/role configuration for the linked message.',
                KEY_EXAMPLE: '!cb ra reset https://discord.com/URL'
            },
            {
                KEY_EMOJI: '📨',
                KEY_TITLE: 'copy [source message link] [destination message link]',
                KEY_DESCRIPTION: 'Copies the reaction/role config from the source message to the destination message.',
                KEY_EXAMPLE: '!cb ra copy https://discord.com/SRC https://discord.com/DST'
            }
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.cache_lock = asyncio.Lock()
        self.role_lock = asyncio.Lock()
        with sqlite3.connect(self.db) as connection:
            c = connection.cursor()
            c.execute(
                '''CREATE TABLE IF NOT EXISTS `reactions` (
                    `message_id` INTEGER PRIMARY KEY UNIQUE,
                    `channel_id` INTEGER,
                    `server_id` INTEGER,
                    `is_reactive` BOOLEAN,
                    `allow_multiselect` BOOLEAN,
                    `allow_cancellation` BOOLEAN,
                    `confirmation_type` INTEGER,
                    `confirmation_channel_id` INTEGER,
                    `reaction_role_menu` TEXT NOT NULL
                );''')
            connection.commit()
            c.close()

    @commands.command(aliases=['reaction', 'ra'])
    async def reactions(self, ctx, command: str = None, *args):
        if self.bot.get_cog('RASession'):
            return  # Message will be handled by the active RASession.
        elif command == 'list' and len(args) == 0:
            await self.list(ctx)
        elif command == 'config' and len(args) == 1:
            await self.config(ctx, args[0])
        elif command == 'reset' and len(args) == 1:
            await self.reset(ctx, args[0])
        elif command == 'copy' and len(args) == 2:
            await self.copy(ctx, args[0], args[1])
        else:
            prefix = get_prefix(self.bot, ctx.message)
            await ctx.send(embed=create_help_embed(self.help, prefix))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.on_raw_reaction_event(event, REACTION_ADD)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        await self.on_raw_reaction_event(event, REACTION_REMOVE)

    async def on_raw_reaction_event(self, event, event_type):
        server = self.bot.get_guild(event.guild_id)
        user = server.get_member(event.user_id)
        if user.bot:
            return
        server_info = await self.get_reaction_roles_for_server(server.id)
        for message_info in server_info:
            if ((event.message_id == message_info[DATA_KEY_MESSAGE_ID])
                    and (event.channel_id == message_info[DATA_KEY_CHANNEL_ID])):
                emoji = str(event.emoji)
                if emoji in message_info[DATA_KEY_REACTION_ROLES]:
                    channel = server.get_channel(message_info[DATA_KEY_CHANNEL_ID])
                    message = await channel.fetch_message(message_info[DATA_KEY_MESSAGE_ID])
                    log(f'{user.name}#{user.discriminator} {"" if event_type == REACTION_ADD else "un-"}'
                        f'reacted to message {message.id} with "{emoji}".')
                    await self.handle_reaction_event(message, user, emoji, event_type)

    async def handle_reaction_event(self, message, user, emoji, event_type):
        config = await self.get_config_for_message(message)
        role = Reactions.get_role_from_config(config, emoji, message.guild)

        if not role:
            log(f'ERROR: Nonexistent role in {config[KEY_MESSAGE_LINK]}!')
            await user.send(embed=create_basic_embed('Something went wrong - that role doesn\'t exist!', EMOJI_ERROR))
            return

        async with self.role_lock:
            if config[KEY_ALLOW_MULTISELECT]:
                # Simple case - multiselect is allowed, so all choices are independent of each other.
                if event_type == REACTION_ADD:
                    await Reactions.handle_single_role_addition(user, role, emoji, config)
                else:
                    await Reactions.handle_single_role_removal(user, role, emoji, config)
            elif (event_type == REACTION_ADD) and config[KEY_ALLOW_CANCELLATION]:
                # Before adding the role, remove all other role options and reactions available in the message.
                # Removing the reactions like this will trigger a new REACTION_REMOVE event.
                for reaction_option in message.reactions:
                    if reaction_option.emoji != emoji:
                        role_option = Reactions.get_role_from_config(config, reaction_option.emoji, message.guild)
                        if role_option in user.roles:
                            log(f'Removing role "{role_option.name}" from {user.name}#{user.discriminator}.', indent=1)
                            await user.remove_roles(role_option)
                            log(f'Removing {user.name}#{user.discriminator}\'s "{reaction_option.emoji}" '
                                f'reaction from message {message.id}.', indent=1)
                            await reaction_option.remove(user)
                await Reactions.handle_single_role_addition(user, role, emoji, config)
            elif (event_type == REACTION_ADD) and (not config[KEY_ALLOW_CANCELLATION]):
                # Only add the role if the user has not already selected a role from the message.
                # Also remove the current reaction if it's invalid, which will trigger a new REACTION_REMOVE event.
                # TODO: Optimize this! We probably don't need to loop through twice.
                role_reaction_map = {}
                for reaction_option in message.reactions:
                    role_option = Reactions.get_role_from_config(config, reaction_option.emoji, message.guild)
                    if role_option:
                        role_reaction_map[role_option] = reaction_option
                already_selected_role = None
                for role_option, reaction_option in role_reaction_map.items():
                    if role_option in user.roles:
                        already_selected_role = role_option
                    if reaction_option.emoji == emoji:
                        current_reaction = reaction_option
                if already_selected_role and (role_reaction_map[already_selected_role].emoji != current_reaction.emoji):
                    log(f'{user.name}#{user.discriminator} has already selected the "{already_selected_role.name}" '
                        f'role, and switching is disabled.', indent=1)
                    await current_reaction.remove(user)
                    await user.send(embed=create_basic_embed(
                        TEXT_ALREADY_SELECTED_FORMAT.format(config[KEY_MESSAGE_LINK], already_selected_role.name)))
                else:
                    await Reactions.handle_single_role_addition(user, role, emoji, config)
            elif event_type == REACTION_REMOVE:
                # This case might be triggered when the bot auto-removes users' reactions in the cases above, so we
                # should only process the role removal here if the role hasn't already been removed from the user.
                if role in user.roles:
                    await Reactions.handle_single_role_removal(user, role, emoji, config)
                else:
                    log(f'{user.name}#{user.discriminator} already doesn\'t have the role "{role.name}".', indent=1)
            else:
                # This should never happen, but log it just in case it does.
                log(f'ERROR: Unexpected event type or message config!')
                log(f'SOURCE: {user.name}#{user.discriminator} {"" if event_type == REACTION_ADD else "un-"}'
                    f'reacted with "{emoji}".', indent=1)
                log(f'CONFIG: {config}', indent=1)
                await user.send(
                    embed=create_basic_embed('Something went wrong - that\'s an unexpected event type!', EMOJI_ERROR))

    # This method assumes that self.role_lock is already held by the caller.
    @staticmethod
    async def handle_single_role_addition(user, role, emoji, config):
        message_link = config[KEY_MESSAGE_LINK]
        if role in user.roles:
            log(f'{user.name}#{user.discriminator} already has the role "{role.name}".', indent=1)
            if config[KEY_ALLOW_CANCELLATION]:
                await user.send(embed=create_basic_embed(
                    TEXT_ALREADY_REACTED_FORMAT.format(role.name, emoji, message_link)))
            else:
                await user.send(embed=create_basic_embed(TEXT_REDUNDANT_REACTION_FORMAT.format(role.name)))
        else:
            log(f'Adding role "{role.name}" to {user.name}#{user.discriminator}.', indent=1)
            await user.add_roles(role)
            if config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PUBLIC:
                confirmation_channel = role.guild.get_channel(config[KEY_CONFIRMATION_CHANNEL_ID])
                await confirmation_channel.send(embed=create_basic_embed(
                    TEXT_CONFIRMATION_PUBLIC_FORMAT.format(emoji, user.mention, role.mention, message_link)))
            elif config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PRIVATE:
                await user.send(embed=create_basic_embed(
                    TEXT_CONFIRMATION_PRIVATE_FORMAT.format(emoji, role.name, message_link)))

    # This method assumes that self.role_lock is already held by the caller.
    @staticmethod
    async def handle_single_role_removal(user, role, emoji, config):
        message_link = config[KEY_MESSAGE_LINK]
        if role in user.roles:
            if config[KEY_ALLOW_CANCELLATION]:
                log(f'Removing role "{role.name}" from {user.name}#{user.discriminator}.', indent=1)
                await user.remove_roles(role)
                if config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PUBLIC:
                    confirmation_channel = role.guild.get_channel(config[KEY_CONFIRMATION_CHANNEL_ID])
                    await confirmation_channel.send(embed=create_basic_embed(
                        TEXT_CANCELLATION_PUBLIC_FORMAT.format(emoji, user.mention, role.mention, message_link)))
                elif config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PRIVATE:
                    await user.send(embed=create_basic_embed(
                        TEXT_CANCELLATION_PRIVATE_FORMAT.format(emoji, role.name, message_link)))
            else:
                log(f'Cannot remove role "{role.name}" from {user.name}#{user.discriminator} '
                    f'because cancellations are disabled.', indent=1)
                await user.send(embed=create_basic_embed(TEXT_CANCELLATIONS_DISABLED_FORMAT.format(role.name)))
        else:
            log(f'{user.name}#{user.discriminator} already doesn\'t have the role "{role.name}".', indent=1)
            await user.send(embed=create_basic_embed(
                TEXT_ALREADY_UNREACTED_FORMAT.format(role.name, emoji, message_link)))

    # This method assumes that self.cache_lock is already held by the caller.
    def has_fresh_data_for_server(self, server_id):
        if server_id not in self.cache:
            return False
        else:
            cache_timestamp = self.cache[server_id][CACHE_KEY_TIMESTAMP]
            return (datetime.now() - cache_timestamp).seconds < CACHE_TTL_SECONDS

    async def get_reaction_roles_for_server(self, server_id):
        async with self.cache_lock:
            if self.has_fresh_data_for_server(server_id):
                return self.cache[server_id][CACHE_KEY_DATA]

            data_from_db = []
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                query = 'SELECT message_id, channel_id, reaction_role_menu FROM reactions WHERE server_id=?'
                for row in c.execute(query, (server_id,)):
                    data_from_db.append({
                        DATA_KEY_MESSAGE_ID: row[0],
                        DATA_KEY_CHANNEL_ID: row[1],
                        DATA_KEY_REACTION_ROLES: [item[0] for item in json.loads(row[2])]
                    })
                c.close()

            self.cache[server_id] = {
                CACHE_KEY_DATA: data_from_db,
                CACHE_KEY_TIMESTAMP: datetime.now()
            }
            return data_from_db

    async def get_config_for_message(self, message):
        async with self.cache_lock:
            server_id = message.guild.id
            if self.has_fresh_data_for_server(server_id) and message.id in self.cache[server_id]:
                return self.cache[server_id][message.id]

            config = {}
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM reactions WHERE message_id=?', (message.id,))
                row = c.fetchone()
                if row and row[1] == message.channel.id and row[2] == server_id:
                    config[KEY_MESSAGE_LINK] = message.jump_url
                    config[KEY_IS_REACTIVE] = bool(row[3])
                    config[KEY_ALLOW_MULTISELECT] = bool(row[4])
                    config[KEY_ALLOW_CANCELLATION] = bool(row[5])
                    config[KEY_CONFIRMATION_TYPE] = row[6]
                    config[KEY_CONFIRMATION_CHANNEL_ID] = row[7]
                    config[KEY_REACTION_ROLE_MENU] = json.loads(row[8])
                c.close()

            if server_id in self.cache:
                self.cache[server_id][message.id] = config
            return config

    async def save_config_for_message(self, message, config):
        async with self.cache_lock:
            server_id = message.guild.id
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM reactions WHERE message_id=?', (message.id,))
                row = c.fetchone()
                if row and row[1] == message.channel.id and row[2] == server_id:
                    c.execute('UPDATE reactions '
                              'SET is_reactive=?,'
                              '    allow_multiselect=?,'
                              '    allow_cancellation=?,'
                              '    confirmation_type=?,'
                              '    confirmation_channel_id=?,'
                              '    reaction_role_menu=? '
                              'WHERE message_id=?',
                              (config[KEY_IS_REACTIVE], config[KEY_ALLOW_MULTISELECT], config[KEY_ALLOW_CANCELLATION],
                               config[KEY_CONFIRMATION_TYPE], config[KEY_CONFIRMATION_CHANNEL_ID],
                               json.dumps(config[KEY_REACTION_ROLE_MENU]),
                               message.id))
                else:
                    c.execute('INSERT INTO reactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (message.id, message.channel.id, server_id,
                               config[KEY_IS_REACTIVE], config[KEY_ALLOW_MULTISELECT], config[KEY_ALLOW_CANCELLATION],
                               config[KEY_CONFIRMATION_TYPE], config[KEY_CONFIRMATION_CHANNEL_ID],
                               json.dumps(config[KEY_REACTION_ROLE_MENU])))
                c.close()
                self.cache.pop(server_id, None)  # Invalidate the cache because changes were made.

    async def delete_config_for_message(self, server_id, message_id):
        async with self.cache_lock:
            message_deleted = False
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM reactions WHERE message_id=? AND server_id=?', (message_id, server_id))
                if c.fetchone():
                    c.execute('DELETE FROM reactions WHERE message_id=? AND server_id=?', (message_id, server_id))
                    self.cache.pop(server_id, None)  # Invalidate the cache because changes were made.
                    message_deleted = True
                c.close()
            return message_deleted

    @staticmethod
    def get_available_reactions(config):
        return [item[0] for item in config[KEY_REACTION_ROLE_MENU]]

    @staticmethod
    def get_role_str_from_config(config, emoji):
        for reaction, role in config[KEY_REACTION_ROLE_MENU]:
            if reaction == emoji:
                return role

    @staticmethod
    def get_role_from_role_str(role_str, server):
        return server.get_role(int(role_str[3:-1]))

    @staticmethod
    def get_role_from_config(config, emoji, server):
        role_str = Reactions.get_role_str_from_config(config, emoji)
        if role_str:
            return Reactions.get_role_from_role_str(role_str, server)

    @staticmethod
    def get_message_link_string(message_link):
        return f'[{extract_message_id(message_link)}]({message_link})'

    @staticmethod
    def get_display_embed(bot, config):
        if not config or KEY_MESSAGE_LINK not in config:
            raise ValueError(f'Invalid config: {config}')

        title = f'Reaction/Role Configuration'
        description = f'** **\n**Options for message {Reactions.get_message_link_string(config[KEY_MESSAGE_LINK])}:**'
        headers = ('Reaction Emoji', 'Assigned Role')

        if config[KEY_IS_REACTIVE]:
            description += f'\n{EMOJI_OPTION_REACTIVE_TRUE} The message is currently responding to the reactions below!'
        else:
            description += f'\n{EMOJI_OPTION_REACTIVE_FALSE} The message is currently **NOT** responding to reactions.'

        if config[KEY_ALLOW_MULTISELECT]:
            description += f'\n{EMOJI_OPTION_SELECT_MULTIPLE} Users are allowed to select multiple roles.'
        else:
            description += f'\n{EMOJI_OPTION_SELECT_SINGLE} Users are only allowed to select **one** role.'

        if config[KEY_ALLOW_CANCELLATION]:
            description += f'\n{EMOJI_OPTION_CANCELLABLE_TRUE} Users can remove their role(s) by un-reacting.'
        else:
            description += f'\n{EMOJI_OPTION_CANCELLABLE_FALSE} Users cannot remove their role(s) after adding them.'

        if config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PUBLIC:
            channel = bot.get_channel(config[KEY_CONFIRMATION_CHANNEL_ID])
            description += f'\n{EMOJI_OPTION_CONFIRMATION_PUBLIC} ' \
                           f'Messages will be sent to {channel.mention} when users change their roles.'
        elif config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PRIVATE:
            description += f'\n{EMOJI_OPTION_CONFIRMATION_PRIVATE} ' \
                           f'Users will receive a confirmation DM when they select or un-select a role.'
        else:
            description += f'\n{EMOJI_OPTION_CONFIRMATION_NONE} ' \
                           f'Confirmation messages will **NOT** be sent when users select or un-select roles.'

        return create_table_embed(title, headers, config[KEY_REACTION_ROLE_MENU], description, mark_rows=False)

    @staticmethod
    async def validate_message(ctx, message_link, bot_member):
        message = await fetch_message(ctx, message_link)
        if not message:
            await ctx.send(embed=create_basic_embed('I couldn\'t find that message!', EMOJI_ERROR))
        elif not message.channel.permissions_for(bot_member).add_reactions:
            await ctx.send(embed=create_basic_embed("I'm not allowed to add reactions in that channel!", EMOJI_ERROR))
        elif not message.channel.permissions_for(bot_member).manage_messages:
            await ctx.send(embed=create_basic_embed("I'm not allowed to manage messages in that channel!", EMOJI_ERROR))
        else:
            return message

    @staticmethod
    async def ensure_relevant_reactions(message, config):
        if config[KEY_IS_REACTIVE]:
            available_reactions = Reactions.get_available_reactions(config)
            for emoji in available_reactions:
                await message.add_reaction(emoji)  # Make sure all relevant reactions are present.
            for reaction in message.reactions:
                if str(reaction.emoji) not in available_reactions:
                    await message.clear_reaction(reaction.emoji)  # Remove all irrelevant reactions.
        else:
            await message.clear_reactions()

    async def list(self, ctx):
        server_info = await self.get_reaction_roles_for_server(ctx.guild.id)
        table_rows = []

        for message_info in server_info:
            try:
                channel = ctx.guild.get_channel(message_info[DATA_KEY_CHANNEL_ID])
                message = await channel.fetch_message(message_info[DATA_KEY_MESSAGE_ID])
                message_link_string = f'**{Reactions.get_message_link_string(message.jump_url)}**'
                available_reactions = ' \u200B '.join(message_info[DATA_KEY_REACTION_ROLES])
                table_rows.append((channel.mention, message_link_string, available_reactions))
            except (AttributeError, HTTPException):
                await self.delete_config_for_message(ctx.guild.id, message_info[DATA_KEY_MESSAGE_ID])

        title = f'Reaction/Role Messages in "{ctx.guild.name}"'
        headers = ('Channel', 'Message', 'Available Reactions')
        embed = create_table_embed(title, headers, table_rows, mark_rows=False)
        await ctx.send(embed=embed)

    async def config(self, ctx, message_link):
        bot_member = ctx.guild.get_member(self.bot.user.id)
        message = await Reactions.validate_message(ctx, message_link, bot_member)
        if message:
            config = await self.get_config_for_message(message)
            if not config:
                config = {
                    KEY_MESSAGE_LINK: message_link,
                    KEY_IS_REACTIVE: True,
                    KEY_ALLOW_MULTISELECT: True,
                    KEY_ALLOW_CANCELLATION: True,
                    KEY_CONFIRMATION_TYPE: CONFIRMATION_TYPE_PRIVATE,
                    KEY_CONFIRMATION_CHANNEL_ID: ctx.channel.id,
                    KEY_REACTION_ROLE_MENU: []
                }
            display_message = await ctx.send(embed=Reactions.get_display_embed(self.bot, config))
            session_cog = Reactions.RASession(self, ctx, config, display_message)
            self.bot.add_cog(session_cog)
            await session_cog.show_main_menu()

    async def reset(self, ctx, message_link):
        bot_member = ctx.guild.get_member(self.bot.user.id)
        message = await Reactions.validate_message(ctx, message_link, bot_member)
        if message:
            message_link_string = Reactions.get_message_link_string(message_link)
            message_deleted = await self.delete_config_for_message(message.guild.id, message.id)
            if message_deleted:
                for reaction in message.reactions:
                    if reaction.me:
                        await reaction.remove(bot_member)
                embed_msg = f'Deleted reaction/role configuration for message **{message_link_string}**.'
                embed_emoji = EMOJI_SUCCESS
            else:
                embed_msg = f'Message **{message_link_string}** does not have a reaction/role configuration.'
                embed_emoji = EMOJI_WARNING
            await ctx.send(embed=create_basic_embed(embed_msg, embed_emoji))

    async def copy(self, ctx, src_message_link, dst_message_link):
        bot_member = ctx.guild.get_member(self.bot.user.id)
        src_message = await Reactions.validate_message(ctx, src_message_link, bot_member)
        dst_message = await Reactions.validate_message(ctx, dst_message_link, bot_member)

        if src_message and dst_message:
            src_config = await self.get_config_for_message(src_message)
            await self.save_config_for_message(dst_message, src_config)
            await Reactions.ensure_relevant_reactions(dst_message, src_config)

            src_string = Reactions.get_message_link_string(src_message_link)
            dst_string = Reactions.get_message_link_string(dst_message_link)
            embed_msg = f'Copied reaction/role configuration from message **{src_string}** to message **{dst_string}**.'
            await ctx.send(embed=create_basic_embed(embed_msg, EMOJI_SUCCESS))

    class RASession(commands.Cog):
        def __init__(self, parent, ctx, config, display_message):
            self.parent = parent
            self.bot = parent.bot
            self.db = parent.db
            self.ctx = ctx
            self.owner = ctx.author
            self.channel = ctx.channel
            self.config = config.copy()
            self.config[KEY_REACTION_ROLE_MENU] = config[KEY_REACTION_ROLE_MENU].copy()
            self.staging_config = None
            self.display_message = display_message
            self.reactive_message_id = 0
            self.expected_emoji = []
            self.messages_to_delete = set()

        def check_reaction(self, reaction, user):
            is_emoji_expected = (not self.expected_emoji) or (str(reaction.emoji) in self.expected_emoji)
            is_emoji_allowed = (not reaction.custom_emoji) or (user.id in SUPER_USERS)
            is_emoji_valid = is_emoji_expected and is_emoji_allowed
            return (user.id == self.owner.id) and (reaction.message.id == self.reactive_message_id) and is_emoji_valid

        def check_message(self, message):
            return message.author.id == self.owner.id and message.channel.id == self.channel.id

        @commands.Cog.listener()
        async def on_message(self, message):
            if self.check_message(message) and self.reactive_message_id:
                embed_text = f'{message.author.mention}, please react to my message above!'
                info_message = await message.channel.send(embed=create_basic_embed(embed_text, EMOJI_WARNING))
                self.messages_to_delete.update({info_message, message})

        async def prompt_for_reaction(
                self, reactive_message, callback, emoji_list=None, accept_any_emoji=False, extra_data=None):
            self.reactive_message_id = reactive_message.id

            if (not accept_any_emoji) and (emoji_list is not None):
                self.expected_emoji = emoji_list.copy()

            for emoji in emoji_list:
                await reactive_message.add_reaction(emoji)

            try:
                reaction, unused_user = \
                    await self.bot.wait_for('reaction_add', timeout=SESSION_TIMEOUT_SECONDS, check=self.check_reaction)
            except asyncio.TimeoutError:
                if self.reactive_message_id != self.display_message.id:
                    self.messages_to_delete.update({reactive_message})
                else:
                    await self.display_message.clear_reactions()
                await self.finish(create_basic_embed(TEXT_SESSION_TIMEOUT, EMOJI_ERROR))
            else:
                self.reactive_message_id = 0
                self.expected_emoji.clear()
                await reactive_message.clear_reactions()
                await callback(str(reaction), reactive_message, extra_data)

        async def prompt_for_message(self, prompt_message, callback, extra_data=None):
            try:
                user_message = \
                    await self.bot.wait_for('message', timeout=SESSION_TIMEOUT_SECONDS, check=self.check_message)
            except asyncio.TimeoutError:
                self.messages_to_delete.update({prompt_message})
                await self.finish(create_basic_embed(TEXT_SESSION_TIMEOUT, EMOJI_ERROR))
            else:
                await prompt_message.delete()
                await callback(user_message, extra_data)

        async def show_main_menu(self):
            main_menu_message = await self.channel.send(embed=create_basic_embed(TEXT_MAIN_MENU))
            await self.prompt_for_reaction(
                main_menu_message,
                self.main_menu_callback,
                [
                    EMOJI_EDIT_MESSAGE_OPTIONS,
                    EMOJI_EDIT_REACTION_ROLES,
                    EMOJI_EDIT_CHANNEL,
                    EMOJI_SUCCESS,
                    EMOJI_ERROR
                ])

        async def show_role_prompt(self, emoji):
            embed_text = '**What is the name/id of the role you want to associate with this emoji?**\nYou may also ' \
                         'tag the role, but be aware that doing so will ping the people with that role in this channel.'
            prompt_message = await self.channel.send(embed=create_basic_embed(embed_text, emoji))
            await self.prompt_for_message(prompt_message, self.add_or_update_reaction_role_callback, emoji)

        async def update_message_options_menu(self, prompt_message):
            await self.prompt_for_reaction(
                self.display_message,
                self.message_options_callback,
                [
                    EMOJI_OPTIONS[KEY_IS_REACTIVE][self.staging_config[KEY_IS_REACTIVE]],
                    EMOJI_OPTIONS[KEY_ALLOW_MULTISELECT][self.staging_config[KEY_ALLOW_MULTISELECT]],
                    EMOJI_OPTIONS[KEY_ALLOW_CANCELLATION][self.staging_config[KEY_ALLOW_CANCELLATION]],
                    EMOJI_OPTIONS[KEY_CONFIRMATION_TYPE][self.staging_config[KEY_CONFIRMATION_TYPE]],
                    EMOJI_SUCCESS,
                    EMOJI_ERROR
                ],
                extra_data=prompt_message)

        async def main_menu_callback(self, emoji, main_menu_message, unused_extra_data):
            await main_menu_message.delete();
            if emoji == EMOJI_EDIT_MESSAGE_OPTIONS:
                self.staging_config = self.config.copy()
                message_link = self.display_message.jump_url
                embed_text = f'**Editing options in message {Reactions.get_message_link_string(message_link)}.**\n' \
                             f'Please react to the above message with the emoji corresponding to the option(s) ' \
                             f'you\'d like to toggle - your changes will be reflected above immediately, ' \
                             f'but will not take effect until you save them. When you\'re finished, react with ' \
                             f'\u200B {EMOJI_SUCCESS} \u200B to save your changes, or react with ' \
                             f'\u200B {EMOJI_ERROR} \u200B to cancel any changes.'
                prompt_message = await self.channel.send(embed=create_basic_embed(embed_text, emoji))
                await self.update_message_options_menu(prompt_message)
            elif emoji == EMOJI_EDIT_REACTION_ROLES:
                embed_text = 'Please react with the emoji corresponding to the reaction/role you\'d like to edit, ' \
                             'or react with a new (non-custom) emoji if you would like to assign a role to it.'
                prompt_message = await self.channel.send(embed=create_basic_embed(embed_text, emoji))
                existing_reactions = Reactions.get_available_reactions(self.config)
                await self.prompt_for_reaction(
                    prompt_message, self.main_reaction_role_callback, existing_reactions, accept_any_emoji=True)
            elif emoji == EMOJI_EDIT_CHANNEL:
                if self.config[KEY_CONFIRMATION_TYPE] == CONFIRMATION_TYPE_PUBLIC:
                    current_channel = self.ctx.guild.get_channel(self.config[KEY_CONFIRMATION_CHANNEL_ID]).mention
                    embed_text = f'**Confirmation messages are currently being posted in **{current_channel}**.**'
                    embed_emoji = EMOJI_OPTION_CONFIRMATION_PUBLIC
                else:
                    embed_text = f'**Role confirmation messages are currently NOT being posted publicly.**'
                    embed_emoji = '🤫'
                embed_text += '\nIf you would like to change this, please tag the channel to which these messages ' \
                              'should be sent. Otherwise, type anything else to cancel this change.'
                prompt_message = await self.channel.send(embed=create_basic_embed(embed_text, embed_emoji))
                await self.prompt_for_message(prompt_message, self.change_channel_callback)
            elif emoji == EMOJI_SUCCESS:
                await self.save_config_changes()
            else:
                embed_text = 'Canceled the reaction/role config session and reverted any changes.'
                await self.finish(create_basic_embed(embed_text, emoji))

        async def message_options_callback(self, emoji, display_message, prompt_message):
            key, value = Reactions.RASession.get_next_option(emoji)
            if key:
                self.staging_config[key] = value
                await display_message.edit(embed=Reactions.get_display_embed(self.bot, self.staging_config))
                await self.update_message_options_menu(prompt_message)
            else:
                if emoji == EMOJI_SUCCESS:
                    embed_text = f'Successfully updated options! \u200B \u200B \u200B ' \
                                 f'{Reactions.RASession.get_emoji_options_string(self.config)}' \
                                 f' \u200B \u200B \u200B \u200B ➡️ \u200B \u200B \u200B \u200B ' \
                                 f'{Reactions.RASession.get_emoji_options_string(self.staging_config)}'
                    await self.channel.send(embed=create_basic_embed(embed_text, emoji))
                    self.config = self.staging_config.copy()
                else:
                    self.staging_config = None
                    await display_message.edit(embed=Reactions.get_display_embed(self.bot, self.config))
                    embed_text = f'Reverted back to the previous options: \u200B \u200B ' \
                                 f'{Reactions.RASession.get_emoji_options_string(self.config)}'
                    cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                    self.messages_to_delete.update({cancellation_message})
                await prompt_message.delete()
                await self.show_main_menu()

        async def main_reaction_role_callback(self, emoji, old_prompt_message, unused_extra_data):
            await old_prompt_message.delete()
            if emoji in Reactions.get_available_reactions(self.config):
                role = Reactions.get_role_str_from_config(self.config, emoji)
                embed_text = f'**Editing the \u200B {emoji} \u200B reaction, currently assigned to ' \
                             f'the **{role}** role.** {TEXT_REACTION_ROLE_MENU}'
                new_prompt_message = await self.channel.send(embed=create_basic_embed(embed_text))
                await self.prompt_for_reaction(
                    new_prompt_message,
                    self.edit_or_delete_reaction_role_callback,
                    [EMOJI_ROLE_EDIT, EMOJI_ROLE_DELETE, EMOJI_ERROR],
                    extra_data=[emoji, role])
            else:
                await self.show_role_prompt(emoji)

        async def edit_or_delete_reaction_role_callback(self, action_emoji, old_prompt_message, current_pairing):
            reaction_emoji, role = current_pairing
            await old_prompt_message.delete()
            if action_emoji == EMOJI_ROLE_EDIT:
                await self.show_role_prompt(reaction_emoji)
            elif action_emoji == EMOJI_ROLE_DELETE:
                self.config[KEY_REACTION_ROLE_MENU].remove(current_pairing)
                await self.display_message.edit(embed=Reactions.get_display_embed(self.bot, self.config))
                embed_text = f'Reacting with \u200B {reaction_emoji} \u200B will no longer grant the {role} role.'
                await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_SUCCESS))
                await self.show_main_menu()
            else:
                embed_text = f'No changes made to the \u200B {reaction_emoji} \u200B reaction.'
                cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                self.messages_to_delete.update({cancellation_message})
                await self.show_main_menu()

        async def add_or_update_reaction_role_callback(self, user_message, emoji):
            role = Reactions.RASession.get_role_from_server(self.channel.guild, user_message.content)
            if role:
                Reactions.RASession.update_reaction_role(self.config[KEY_REACTION_ROLE_MENU], (emoji, role.mention))
                await self.display_message.edit(embed=Reactions.get_display_embed(self.bot, self.config))
                embed_text = f'Reacting with \u200B {emoji} \u200B will now grant the {role.mention} role.'
                await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_SUCCESS))
            else:
                embed_text = f'Could not find a role matching **"{user_message.content}"**. No changes made.'
                cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                self.messages_to_delete.update({cancellation_message})
            await user_message.delete()
            await self.show_main_menu()

        async def change_channel_callback(self, user_message, unused_extra_data):
            if len(user_message.channel_mentions) == 1:
                channel = user_message.channel_mentions[0]
                self.config[KEY_CONFIRMATION_TYPE] = CONFIRMATION_TYPE_PUBLIC
                self.config[KEY_CONFIRMATION_CHANNEL_ID] = channel.id
                await self.display_message.edit(embed=Reactions.get_display_embed(self.bot, self.config))
                embed_text = f'Role confirmation messages will now be posted in {channel.mention}.'
                await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_SUCCESS))
            else:
                embed_text = f'Could not find a channel matching **"{user_message.content}"**. No changes made.'
                cancellation_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
                self.messages_to_delete.update({cancellation_message})
            await user_message.delete()
            await self.show_main_menu()

        async def save_config_changes(self):
            message_link = self.config[KEY_MESSAGE_LINK]
            message = await fetch_message(self.ctx, message_link)
            existing_config = await self.parent.get_config_for_message(message)

            if list(existing_config.values()) == list(self.config.values()):
                embed = create_basic_embed('Config session ended. You didn\'t make any changes!', '🤨')
            else:
                await self.parent.save_config_for_message(message, self.config)
                embed_text = f'Your changes have been saved and are now live. [Check it out!]({message_link})'
                embed = create_basic_embed(embed_text, '🥳')

            await Reactions.ensure_relevant_reactions(message, self.config)
            await self.finish(embed)

        @staticmethod
        def update_reaction_role(reaction_role_menu, new_reaction_role_pair):
            for i in range(len(reaction_role_menu)):
                reaction, role = reaction_role_menu[i]
                if reaction == new_reaction_role_pair[0]:
                    reaction_role_menu[i] = new_reaction_role_pair
                    return
            reaction_role_menu.append(new_reaction_role_pair)

        @staticmethod
        def get_emoji_options_string(config):
            emoji_string = ''
            for key, values in EMOJI_OPTIONS.items():
                emoji_string += ' ' + values[config[key]]
            return emoji_string.strip()

        @staticmethod
        def get_next_option(emoji):
            for key, values in EMOJI_OPTIONS.items():
                if emoji in values:
                    next_index = (values.index(emoji) + 1) % len(values)
                    value = next_index if key == KEY_CONFIRMATION_TYPE else bool(next_index)
                    return key, value
            return None, None

        @staticmethod
        def get_role_from_server(server, role_str):
            role_str = ' '.join(role_str.split())
            for role in server.roles:
                if (role_str == role.mention) or (role_str == str(role.id)) or (role_str.lower() == role.name.lower()):
                    return role

        async def finish(self, embed):
            await self.channel.delete_messages(self.messages_to_delete)
            await self.channel.send(embed=embed)
            self.bot.remove_cog('RASession')


def setup(bot):
    bot.add_cog(Reactions(bot))
