from aiosqlite import connect
from asyncio import Lock
from dataclasses import dataclass, field
from discord import Embed, Guild, TextChannel
from discord.ext.commands import Bot, Cog, Context, command
from json import dumps, loads
from lib.embeds import *
from lib.permission import Permission
from lib.prefixes import get_prefix
from lib.utils import log

EMOJI_PERMISSION_DETAILS = '🔍'
EMOJI_PERMISSION_DISABLED = '⛔'
EMOJI_PERMISSION_ENABLED = '✅'
EMOJI_PERMISSION_RESTRICTED = '🤫'

ERROR_INVALID_COMMAND_TEXT_FORMAT = '`{0}` \u200B is not a valid command. Please try again!'  # arg: command
ERROR_INVALID_COMMAND_HINT_FORMAT = 'To see a list of available commands, type: \u200B `{0}permissions`'  # arg: prefix
ERROR_INVALID_PERMISSION_TEXT_FORMAT = '`{0}` \u200B is not a valid permission. Please try again!'  # arg: permission
ERROR_INVALID_PERMISSION_HINT_FORMAT = 'To see all available permissions, type: \u200B `{0}pm overview`'  # arg: prefix
ERROR_UNSPECIFIED_PERMISSION_FORMAT = 'Please specify a permission for the \u200B `{0}` \u200B command.'  # arg: command
ERROR_INVALID_CHANNEL_FORMAT = 'I don\'t have permission to send messages in {0}!'  # arg: channel_mention
ERROR_UNSPECIFIED_CHANNEL = 'Please specify at least one channel for the \u200B `toggle` \u200B command.'

OVERVIEW_TITLE_FORMAT = 'Permissions Overview for "{0}"'  # arg: server_name
OVERVIEW_DISABLED_HEADER = f'{EMOJI_PERMISSION_DISABLED} \u200B Disabled'
OVERVIEW_ENABLED_HEADER = f'{EMOJI_PERMISSION_ENABLED} \u200B Enabled'
OVERVIEW_RESTRICTED_HEADER = f'{EMOJI_PERMISSION_RESTRICTED} \u200B Restricted'
OVERVIEW_PERMISSION_FORMAT = '`{0}`'  # arg: permission_name
OVERVIEW_EMPTY_VALUE = '✖️ \u200B *None!*'
OVERVIEW_DESCRIPTION = 'This is a high-level summary that sorts all available permissions into the following ' \
                       'categories, which represent the permission\'s current status in this server:\n' \
                       f'\n{TEXT_INDENT_SPACING * 2} **{OVERVIEW_ENABLED_HEADER}:** \u200B ' \
                       'The permission is enabled in **ALL** channels.' \
                       f'\n{TEXT_INDENT_SPACING * 2} **{OVERVIEW_RESTRICTED_HEADER}:** \u200B ' \
                       'The permission is enabled in specific whitelisted channels.' \
                       f'\n{TEXT_INDENT_SPACING * 2} **{OVERVIEW_DISABLED_HEADER}:** \u200B ' \
                       'The permission is disabled in this server.' \
                       '\n\nFor more information about a specific permission, use the \u200B `details` \u200B command.'

DETAILS_TITLE_FORMAT = '**Permission Details for** \u200B `{0}`'  # arg: permission_name
DETAILS_STATUS_LABEL_FORMAT = '\n\n**Status:** \u200B {0} '  # arg: status_emoji
DETAILS_STATUS_DISABLED_FORMAT = 'Disabled for all channels in **"{0}"**.'  # arg: server_name
DETAILS_STATUS_ENABLED_FORMAT = 'Enabled for **ALL** channels in **"{0}"**.'  # arg: server_name
DETAILS_STATUS_RESTRICTED_SINGULAR_FORMAT = 'Only enabled in the <#{0}> channel.'  # arg: channel_id
DETAILS_STATUS_RESTRICTED_PLURAL = f'Only enabled in the following channels:\n{TEXT_INDENT_SPACING * 5}'
DETAILS_COMMANDS_LABEL = '\n\n**Associated Commands:** '
DETAILS_COMMANDS_VISIBLE_FORMAT = '\u200B `{0}{1}`'  # args: prefix, command
DETAILS_COMMANDS_HIDDEN = ' \u200B Unspecified. *(It\'s a secret!)*'

UPDATE_WARNING_NO_CHANGES = 'That command doesn\'t make any changes to the current permission settings.'
UPDATE_DISABLED_FORMAT = 'The `{0}` permission is now disabled for all channels.'  # arg: permission_name
UPDATE_ENABLED_FORMAT = 'The `{0}` permission is now enabled for all channels!'  # arg: permission_name
UPDATE_RESTRICTED_FORMAT = 'The `{0}` permission is now enabled in these channels:' \
                           f'\n{TEXT_INDENT_SPACING * 3}'  # arg: permission_name
UPDATE_CORE_FUNCTION_FORMAT = '`{0}` \u200B is one of my core functions - I can\'t let you disable it!' \
                              f'\n{TEXT_INDENT_SPACING * 3}To restrict this permission to specific ' \
                              'channels, use the \u200B `toggle` \u200B command.'  # arg: permission_name


@dataclass(frozen=True)
class PermissionConfig:
    """ Represents a specific configuration of settings for a CirqueBot permission in the current server.

    This data class is fully immutable and contains only two fields: "is_enabled" and "whitelisted_channel_ids".

    These fields cohesively express three possible "states" for the permission:
        - If "is_enabled" is TRUE and "whitelisted_channel_ids" is EMPTY, then the permission is "ENABLED".
            This means it is usable in ALL CHANNELS in the current server.
        - If "is_enabled" is TRUE and "whitelisted_channel_ids" is NON-EMPTY, then the permission is "RESTRICTED".
            This means it is usable in AT LEAST ONE CHANNEL in the current server.
            The channels in which it is usable are specified by the integer IDs in "whitelisted_channel_ids".
        - If "is_enabled" is FALSE, then the permission is "DISABLED".
            This means it is usable in NO CHANNELS (i.e. it is not usable) in the current server.
            In this case, the value of "whitelisted_channel_ids" is irrelevant (but for good practice, should be EMPTY).
    """

    is_enabled: bool
    whitelisted_channel_ids: frozenset = field(default_factory=frozenset)

    @staticmethod
    def get_config(is_enabled: bool, whitelisted_channel_ids: frozenset):
        if whitelisted_channel_ids:
            # Only create a new PermissionConfig object if it's necessary to do so (i.e. the whitelist is non-empty).
            return PermissionConfig(is_enabled=is_enabled, whitelisted_channel_ids=whitelisted_channel_ids)
        else:
            # If the whitelist is empty, simply reuse one of the "constant" PermissionConfig objects.
            return PERMISSION_CONFIG_ENABLED if is_enabled else PERMISSION_CONFIG_DISABLED

    @staticmethod
    def get_default_config_for_permission(permission: Permission):
        # Only the permissions related to core bot functionality are enabled by default.
        return PERMISSION_CONFIG_ENABLED if permission.is_core_function else PERMISSION_CONFIG_DISABLED

    def get_channel_whitelist_display_text(self):
        return ' '.join(f'\u200B<#{channel_id}>' for channel_id in self.whitelisted_channel_ids)


# Reuse these "constants" whenever possible to minimize the number of created PermissionConfig objects.
PERMISSION_CONFIG_ENABLED = PermissionConfig(is_enabled=True)
PERMISSION_CONFIG_DISABLED = PermissionConfig(is_enabled=False)

# An immutable unordered set containing all recognized permission names, for fast validity checking.
VALID_PERMISSION_NAMES = frozenset(permission.name for permission in Permission)


class Permissions(Cog):
    db = 'data/permissions.db'
    help = {
        KEY_EMOJI: '🔐',
        KEY_TITLE: 'Permissions',
        KEY_DESCRIPTION: 'Manages & enforces restrictions for specific commands (configurable per channel).',
        KEY_COMMAND: '!cb permissions',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🧾',
                KEY_TITLE: 'overview',
                KEY_DESCRIPTION: 'Displays a summary of the current settings for all permissions in this server.',
                KEY_EXAMPLE: '!cb pm overview'
            },
            {
                KEY_EMOJI: EMOJI_PERMISSION_DETAILS,
                KEY_TITLE: 'details [permission name]',
                KEY_DESCRIPTION: 'Displays detailed information about the given permission in this server.',
                KEY_EXAMPLE: '!cb pm details ALLOW_BONKS'
            },
            {
                KEY_EMOJI: EMOJI_PERMISSION_ENABLED,
                KEY_TITLE: 'enable [permission name]',
                KEY_DESCRIPTION: 'Enables the given permission for all channels in this server.',
                KEY_EXAMPLE: '!cb pm enable SNIPE_DELETED_MESSAGES'
            },
            {
                KEY_EMOJI: EMOJI_PERMISSION_DISABLED,
                KEY_TITLE: 'disable [permission name]',
                KEY_DESCRIPTION: 'Disables the given permission for all channels in this server.',
                KEY_EXAMPLE: '!cb pm disable VIEW_REACTION_ROLES'
            },
            {
                KEY_EMOJI: '🔧',
                KEY_TITLE: 'toggle [permission name] [channel tag]',
                KEY_DESCRIPTION: 'Toggles the inclusion of the specified channel in the whitelist for the permission.',
                KEY_EXAMPLE: '!cb pm toggle CHANGE_GREETINGS #bot-commands'
            }
        ]
    }

    def __init__(self, bot: Bot):
        self.bot = bot
        self.cache = {}
        self.cache_lock = Lock()
        self.bot.loop.create_task(self.initialize_database())

    async def initialize_database(self):
        async with connect(self.db) as connection:
            cursor = await connection.execute(
                '''CREATE TABLE IF NOT EXISTS `permissions` (
                    `server_id` INTEGER,
                    `permission_id` INTEGER,
                    `is_enabled` BOOLEAN,
                    `whitelisted_channel_ids` TEXT NOT NULL,
                    PRIMARY KEY (`server_id`, `permission_id`)
                );''')
            await connection.commit()
            await cursor.close()

    @command(aliases=['permission', 'perms', 'perm', 'pm'])
    async def permissions(self, ctx: Context, command: str = None, *args):
        prefix = get_prefix(self.bot, ctx.message)

        # The VIEW_PERMISSIONS permission is required for all commands in this module.
        if not await Permissions.check(self.bot, Permission.VIEW_PERMISSIONS, ctx.guild, ctx.channel):
            await ctx.send(embed=create_error_embed(TEXT_MISSING_PERMISSION))
            return

        if (not command) or (command == 'help'):
            await ctx.send(embed=create_help_embed(self.help, prefix))
            return

        # Many aliases for this command are given in case the user gets confused about where to find permission names.
        if command in ('overview', 'ov', 'list', 'ls', 'all', 'names'):
            await self.show_overview(ctx)
            return

        # If a permission name is given as a "command" with no arguments, just show the details for that permission.
        if command and (command.upper() in VALID_PERMISSION_NAMES) and (not args):
            await self.show_details(ctx, Permission[command.upper()])
            return

        if command not in ('details', 'enable', 'disable', 'toggle'):
            error_text = ERROR_INVALID_COMMAND_TEXT_FORMAT.format(command)
            error_hint = ERROR_INVALID_COMMAND_HINT_FORMAT.format(prefix)
            await ctx.send(embed=create_error_embed(error_text, error_hint))
            return

        # All remaining possible commands require a permission name to be specified, so try to form one out of the args.
        possible_permission_name = '_'.join(arg for arg in args if '#' not in arg).replace(' ', '_').upper()

        if not possible_permission_name:
            await ctx.send(embed=create_error_embed(ERROR_UNSPECIFIED_PERMISSION_FORMAT.format(command)))
            return

        if possible_permission_name not in VALID_PERMISSION_NAMES:
            error_text = ERROR_INVALID_PERMISSION_TEXT_FORMAT.format(possible_permission_name)
            error_hint = ERROR_INVALID_PERMISSION_HINT_FORMAT.format(prefix)
            await ctx.send(embed=create_error_embed(error_text, error_hint))
            return

        # This is guaranteed to be a valid permission because all of the above checks have passed.
        target_permission = Permission[possible_permission_name]

        if command == 'details':
            await self.show_details(ctx, target_permission)
            return

        # The CHANGE_PERMISSIONS permission is required for all remaining possible commands.
        if not await Permissions.check(self.bot, Permission.CHANGE_PERMISSIONS, ctx.guild, ctx.channel):
            await ctx.send(embed=create_error_embed(TEXT_MISSING_PERMISSION))
        elif command == 'enable':
            await self.enable_permission(ctx, target_permission)
        elif command == 'disable':
            await self.disable_permission(ctx, target_permission)
        elif command == 'toggle' and ctx.message.channel_mentions:
            await self.toggle_permission_for_channel(ctx, target_permission, ctx.message.channel_mentions)
        else:
            await ctx.send(embed=create_error_embed(ERROR_UNSPECIFIED_CHANNEL))

    @staticmethod
    async def check(bot: Bot, permission: Permission, server: Guild, channel: TextChannel) -> bool:
        """ This gets called from other cogs to determine whether a permission is granted in the given server/channel.
        """
        if (not server) or (not channel):
            log('ERROR: Permissions are only available in server channels. DMs are not recognized.')
            return False

        permission_config = await bot.get_cog('Permissions').get_permission_config_for_server(server.id, permission)

        if not permission_config.is_enabled:
            log(f'WARNING: Permission "{permission.name}" is disabled for all channels in "{server.name}".')
            return False

        whitelisted_channel_ids = permission_config.whitelisted_channel_ids
        if whitelisted_channel_ids and (channel.id not in whitelisted_channel_ids):
            log(f'WARNING: "{channel.name}" is not whitelisted for {permission.name} in "{server.name}".')
            log(f'Whitelisted channel IDs for {permission.name}: {list(whitelisted_channel_ids)}', indent=1)
            return False

        # All checks have been passed - the permission is granted.
        return True

    @staticmethod
    async def announce_permission_updates(ctx: Context, update_text: str, emoji: str):
        if update_text == UPDATE_WARNING_NO_CHANGES:
            emoji = EMOJI_WARNING
        else:
            log(f'INFO: A permission has been updated in "{ctx.guild.name}":')
            log(update_text.replace(f'\n{TEXT_INDENT_SPACING * 3}', ' '), indent=1)
        await ctx.send(embed=create_basic_embed(update_text, emoji))

    async def show_overview(self, ctx: Context):
        server = ctx.guild
        enabled_permissions = []
        restricted_permissions = []
        disabled_permissions = []

        def add_permission(permission_to_add: Permission, permission_list: list):
            permission_list.append(OVERVIEW_PERMISSION_FORMAT.format(permission_to_add.name))

        def add_field(parent_embed: Embed, header: str, permission_list: list):
            field_value = '\n'.join(permission_list) if permission_list else OVERVIEW_EMPTY_VALUE
            parent_embed.add_field(name=header, value=field_value)

        for permission in Permission:
            permission_config = await self.get_permission_config_for_server(server.id, permission)
            if not permission_config.is_enabled:
                add_permission(permission, disabled_permissions)
            elif not permission_config.whitelisted_channel_ids:
                add_permission(permission, enabled_permissions)
            else:
                add_permission(permission, restricted_permissions)

        embed = create_icon_embed(server.icon_url, OVERVIEW_TITLE_FORMAT.format(server.name), OVERVIEW_DESCRIPTION)
        embed.add_field(name='** **', value='** **', inline=False)  # Add space between the description and the lists.
        add_field(embed, OVERVIEW_ENABLED_HEADER, enabled_permissions)
        add_field(embed, OVERVIEW_RESTRICTED_HEADER, restricted_permissions)
        add_field(embed, OVERVIEW_DISABLED_HEADER, disabled_permissions)
        await ctx.send(embed=embed)

    async def show_details(self, ctx: Context, permission: Permission):
        server = ctx.guild
        permission_config = await self.get_permission_config_for_server(server.id, permission)
        embed_text = DETAILS_TITLE_FORMAT.format(permission.name)

        if not permission_config.is_enabled:
            embed_text += DETAILS_STATUS_LABEL_FORMAT.format(EMOJI_PERMISSION_DISABLED)
            embed_text += DETAILS_STATUS_DISABLED_FORMAT.format(server.name)
        elif not permission_config.whitelisted_channel_ids:
            embed_text += DETAILS_STATUS_LABEL_FORMAT.format(EMOJI_PERMISSION_ENABLED)
            embed_text += DETAILS_STATUS_ENABLED_FORMAT.format(server.name)
        else:
            embed_text += DETAILS_STATUS_LABEL_FORMAT.format(EMOJI_PERMISSION_RESTRICTED)
            if len(permission_config.whitelisted_channel_ids) == 1:
                whitelisted_channel_id = next(iter(permission_config.whitelisted_channel_ids))
                embed_text += DETAILS_STATUS_RESTRICTED_SINGULAR_FORMAT.format(whitelisted_channel_id)
            else:
                embed_text += DETAILS_STATUS_RESTRICTED_PLURAL + permission_config.get_channel_whitelist_display_text()

        embed_text += DETAILS_COMMANDS_LABEL
        commands = permission.display_commands

        # TODO: Also display a description of what each of these commands does (e.g. from their 'help' menu).
        if commands:
            prefix = get_prefix(self.bot, ctx.message)
            embed_text += ' '.join(DETAILS_COMMANDS_VISIBLE_FORMAT.format(prefix, command) for command in commands)
        else:
            embed_text += DETAILS_COMMANDS_HIDDEN

        await ctx.send(embed=create_basic_embed(embed_text, EMOJI_PERMISSION_DETAILS))

    async def enable_permission(self, ctx: Context, permission: Permission):
        permission_config = await self.get_permission_config_for_server(ctx.guild.id, permission)

        if permission_config.whitelisted_channel_ids or (not permission_config.is_enabled):
            # The permission is currently restricted or disabled. Enable it for all channels.
            update_text = UPDATE_ENABLED_FORMAT.format(permission.name)
            await self.save_permission_config_for_server(ctx.guild.id, permission, PERMISSION_CONFIG_ENABLED)
        else:
            # The permission is already fully enabled in this server.
            update_text = UPDATE_WARNING_NO_CHANGES

        await Permissions.announce_permission_updates(ctx, update_text, EMOJI_PERMISSION_ENABLED)

    async def disable_permission(self, ctx: Context, permission: Permission):
        if permission.is_core_function:
            await ctx.send(embed=create_basic_embed(UPDATE_CORE_FUNCTION_FORMAT.format(permission.name), '😅'))
            return

        permission_config = await self.get_permission_config_for_server(ctx.guild.id, permission)

        if permission_config.is_enabled:
            # The permission is currently enabled or restricted. Disable it for all channels.
            update_text = UPDATE_DISABLED_FORMAT.format(permission.name)
            await self.save_permission_config_for_server(ctx.guild.id, permission, PERMISSION_CONFIG_DISABLED)
        else:
            # The permission is already fully disabled in this server.
            update_text = UPDATE_WARNING_NO_CHANGES

        await Permissions.announce_permission_updates(ctx, update_text, EMOJI_PERMISSION_DISABLED)

    async def toggle_permission_for_channel(self, ctx: Context, permission: Permission, toggled_channels: list):
        old_permission_config = await self.get_permission_config_for_server(ctx.guild.id, permission)
        toggled_channel_ids = set()

        for channel in toggled_channels:
            if self.is_available_channel(ctx.guild, channel.id):
                toggled_channel_ids.add(channel.id)
            else:
                await ctx.send(embed=create_error_embed(ERROR_INVALID_CHANNEL_FORMAT.format(channel.mention)))
                return

        # Use the symmetric difference set operator (^) to toggle the presence of the given channel(s) in the whitelist.
        new_whitelisted_channel_ids = old_permission_config.whitelisted_channel_ids ^ toggled_channel_ids

        # If the permission was previously enabled or restricted, it will remain in one of those two states (it may
        # swap between them). If the permission was previously disabled, it will become restricted (i.e. only enabled
        # in the specified channel). The result of this behavior is that is_enabled will always be set to True.
        new_permission_config = \
            PermissionConfig.get_config(is_enabled=True, whitelisted_channel_ids=new_whitelisted_channel_ids)

        await self.save_permission_config_for_server(ctx.guild.id, permission, new_permission_config)

        if new_permission_config.whitelisted_channel_ids:
            # The permission is now restricted to the specified whitelisted channels.
            update_text = UPDATE_RESTRICTED_FORMAT.format(permission.name) + \
                          new_permission_config.get_channel_whitelist_display_text()
            update_emoji = EMOJI_PERMISSION_RESTRICTED
        else:
            # The permission is now fully enabled in the server.
            update_text = UPDATE_ENABLED_FORMAT.format(permission.name)
            update_emoji = EMOJI_PERMISSION_ENABLED

        await Permissions.announce_permission_updates(ctx, update_text, update_emoji)

    def is_available_channel(self, server: Guild, channel_id: int) -> bool:
        bot_member = server.get_member(self.bot.user.id)
        channel = server.get_channel(channel_id)
        return channel and channel.permissions_for(bot_member).send_messages

    async def get_permission_config_for_server(self, server_id: int, permission: Permission) -> PermissionConfig:
        async with self.cache_lock:
            if server_id not in self.cache:
                self.cache[server_id] = {}

            if permission.id not in self.cache[server_id]:
                async with connect(self.db) as connection:
                    query = 'SELECT * FROM permissions WHERE server_id=? AND permission_id=?'
                    async with connection.execute(query, (server_id, permission.id)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            server = self.bot.get_guild(server_id)
                            whitelisted_channel_ids = set()
                            for channel_id in loads(row[3]):
                                if self.is_available_channel(server, channel_id):
                                    whitelisted_channel_ids.add(channel_id)
                                else:
                                    log(f'WARNING: Channel {channel_id} in "{server.name}" is no longer available.')
                            permission_config = PermissionConfig.get_config(
                                is_enabled=row[2], whitelisted_channel_ids=frozenset(whitelisted_channel_ids))
                        else:
                            permission_config = PermissionConfig.get_default_config_for_permission(permission)
                self.cache[server_id][permission.id] = permission_config

            return self.cache[server_id][permission.id]

    async def save_permission_config_for_server(
            self, server_id: int, permission: Permission, permission_config: PermissionConfig):
        if permission_config == PermissionConfig.get_default_config_for_permission(permission):
            # Setting to the default config is effectively the same as resetting the config, so favor the simpler path.
            await self.reset_permission_config_for_server(server_id, permission)
            return

        async with self.cache_lock:
            if server_id not in self.cache:
                self.cache[server_id] = {}

            self.cache[server_id][permission.id] = permission_config

            async with connect(self.db) as connection:
                is_enabled = permission_config.is_enabled
                whitelisted_channel_ids = dumps(sorted(permission_config.whitelisted_channel_ids))
                await connection.execute('INSERT INTO permissions'
                                         '    (server_id, permission_id, is_enabled, whitelisted_channel_ids)'
                                         'VALUES (?, ?, ?, ?) '
                                         'ON CONFLICT (server_id, permission_id) '
                                         'DO UPDATE SET is_enabled=?, whitelisted_channel_ids=?',
                                         (server_id, permission.id, is_enabled, whitelisted_channel_ids,
                                          is_enabled, whitelisted_channel_ids))
                await connection.commit()

    async def reset_permission_config_for_server(self, server_id: int, permission: Permission):
        async with self.cache_lock:
            if server_id not in self.cache:
                self.cache[server_id] = {}

            self.cache[server_id][permission.id] = PermissionConfig.get_default_config_for_permission(permission)

            async with connect(self.db) as connection:
                await connection.execute(
                    'DELETE FROM permissions WHERE server_id=? AND permission_id=?', (server_id, permission.id))
                await connection.commit()


def setup(bot: Bot):
    bot.add_cog(Permissions(bot))
