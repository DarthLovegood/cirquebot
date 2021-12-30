from enum import Enum, unique


@unique
class Permission(Enum):
    """ CirqueBot Permission Definitions

    The order of permissions in this file is the order in which they will be displayed to the user when a list of all
    available permissions is requested. Each permission MUST specify a value/id (integer), and may also provide a list
    of "display commands" (strings) that will be shown when detailed information about that permission is requested.

    Some permissions are marked as "core functionality" of CirqueBot. These permissions are necessary in order for
    CirqueBot to function and cannot be fully disabled in any server. However, it is possible to restrict these
    permissions so that they are only enabled in specific channels (see the Permissions cog for more information).

    Once defined, the value/id of a permission must NEVER change. This is because this value is stored in the database
    to represent a specific permission, and changing this mapping could result in broken functionality. Although each
    value must be a unique integer, the actual value is not displayed to the user in any way, so it does not matter if
    the values are out of order in this file. This also means that these permissions can be rearranged and have their
    names changed (if it makes sense to do so) as long as their values are kept the same.

    When adding a new permission to this file, insert it where it makes the most sense, in terms of its category and/or
    functionality. Assign it the "next value" specified on the line below this one, and then update that line.
        NEXT VALUE = 22
    """

    # We override __new__ instead of __init__ because we need to explicitly set the _value_ property.
    def __new__(cls, id: int, display_commands: list = [], is_core_function: bool = False):
        permission = object.__new__(cls)
        permission._value_ = id
        permission.id = id  # An alias for "value" that makes more semantic sense.
        permission.display_commands = display_commands
        permission.is_core_function = is_core_function
        return permission

    # CATEGORY:  Help
    # PROTECTS:  The command for displaying CirqueBot's top-level Help menu.
    # USED IN:   cogs/help.py
    VIEW_HELP = 1, ['help'], True

    # CATEGORY:  Permissions
    # PROTECTS:  Commands related to displaying/managing/enforcing the permissions listed in this file (ooh, meta).
    # USED IN:   cogs/permissions.py
    VIEW_PERMISSIONS = 2, ['pm overview', 'pm details'], True
    CHANGE_PERMISSIONS = 3, ['pm enable', 'pm disable', 'pm toggle'], True

    # CATEGORY:  Prefix
    # PROTECTS:  Commands related to displaying/changing the prefix used by all CirqueBot commands.
    # USED IN:   cogs/prefix.py [TODO: Enforce these permissions.]
    VIEW_PREFIX = 4, ['pf show'], True
    CHANGE_PREFIX = 5, ['pf set', 'pf reset'], True

    # CATEGORY:  Reaction-Roles
    # PROTECTS:  Commands related to displaying/configuring automatic role assignments based on message reactions.
    # USED IN:   cogs/reactions.py [TODO: Enforce these permissions.]
    VIEW_REACTION_ROLES = 6, ['ra list']
    CHANGE_REACTION_ROLES = 7, ['ra config', 'ra copy', 'ra reset']
    CLEANUP_REACTION_ROLES = 8, ['ra cleanup']

    # CATEGORY:  Rewrite
    # PROTECTS:  Commands related to posting/editing collaborative messages that are managed by CirqueBot.
    # USED IN:   cogs/rewrite.py [TODO: Enforce these permissions.]
    POST_RW_MESSAGE = 9, ['rw post']
    CHANGE_RW_MESSAGE = 10, ['rw edit', 'rw replace']

    # CATEGORY:  Greetings
    # PROTECTS:  Commands related to setting/demonstrating automatic messages to be sent when a user joins the server.
    # USED IN:   cogs/greetings.py [TODO: Enforce these permissions.]
    VIEW_GREETINGS = 11, ['gt demo']
    CHANGE_GREETINGS = 12, ['gt config', 'gt reset']

    # CATEGORY:  Sniping
    # PROTECTS:  Commands for retrieving a message/reaction that was deleted/edited by its original author.
    # USED IN:   cogs/sniper.py [TODO: Enforce these permissions.]
    SNIPE_DELETED_MESSAGES = 13, ['snipe']
    SNIPE_EDITED_MESSAGES = 14, ['esnipe']
    SNIPE_REMOVED_REACTIONS = 15, ['rsnipe']

    # CATEGORY:  Audio Playing
    # PROTECTS:  Commands for starting/stopping audio (only whitelisted songs) in a voice channel.
    # USED IN:   cogs/audio_player.py [TODO: Enforce these permissions.]
    START_AUDIO = 16
    STOP_AUDIO = 17, ['stopaudio']

    # CATEGORY:  Easter Eggs
    # PROTECTS:  Commands and functionality tied to various easter eggs that are built into CirqueBot.
    # USED IN:   cogs/easter_eggs.py [TODO: Enforce these permissions.]
    ALLOW_BONKS = 18, ['bonk', 'sunderbonk']
    ALLOW_SPANKS = 19, ['spank']
    ENFORCE_QWEPHESS = 20

    # CATEGORY:  Mini-Games
    # PROTECTS:  Commands for playing mini-games that are built into CirqueBot. Currently in limited beta.
    # USED IN:   cogs/abs_game.py [TODO: Enforce these permissions.]
    PLAY_ABS_GAME = 21
