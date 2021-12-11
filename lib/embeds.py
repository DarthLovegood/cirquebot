from datetime import datetime
from discord import Asset, Embed, User
from lib.prefixes import DEFAULT_PREFIX

COLOR_DEFAULT = 0x9B59B6
COLOR_PUB = 0x2176CD
COLOR_IMP = 0xDE3E3A

EMOJI_ERROR = '❌'
EMOJI_SUCCESS = '✅'
EMOJI_WARNING = '❔'
EMOJI_INFO = 'ℹ'

FORMAT_EMOJI_TEXT = '{0} \u200B \u200B {1}'  # args: emoji, text
FORMAT_HELP_TITLE = 'CirqueBot Help: \u200B \u200B `{0}`'  # args: command
FORMAT_COMMAND_TITLE = '\n** **\n{0} \u200B \u200B {1}'  # args: emoji, title

KEY_TITLE = 'title'
KEY_DESCRIPTION = 'description'
KEY_COMMAND = 'command'
KEY_SUBCOMMANDS = 'subcommands'
KEY_EMOJI = 'emoji'
KEY_EXAMPLE = 'example'


def create_authored_embed(user: User, timestamp: datetime, description: str = ''):
    embed = Embed(timestamp=timestamp, description=description, color=COLOR_DEFAULT)
    embed.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)
    return embed


def create_basic_embed(description: str = '', emoji: str = None):
    if emoji:
        description = FORMAT_EMOJI_TEXT.format(emoji, description)
    return Embed(description=description, color=COLOR_DEFAULT)


def create_event_embed(event: dict):
    # TODO: Implement!
    print(str(event))
    pass


def create_help_embed(help_dict: dict, prefix: str = None):
    if prefix and prefix != DEFAULT_PREFIX:
        help_dict = replace_default_prefix(help_dict, prefix)

    title = FORMAT_HELP_TITLE.format(help_dict[KEY_COMMAND])
    embed = Embed(title=title, description=help_dict[KEY_DESCRIPTION], color=COLOR_DEFAULT)

    for command in help_dict[KEY_SUBCOMMANDS]:
        emoji = command[KEY_EMOJI]
        title = FORMAT_COMMAND_TITLE.format(emoji, command[KEY_TITLE].replace('[', '*[').replace(']', ']*'))
        description = f'{command[KEY_DESCRIPTION]}\n**Example:** `{command[KEY_EXAMPLE]}`'
        embed.add_field(name=title, value=description, inline=False)

    return embed


def create_icon_embed(icon_url: Asset, title: str, description: str = ''):
    embed = Embed(description=description, color=COLOR_DEFAULT)
    embed.set_author(name=title, icon_url=icon_url)
    return embed


def create_table_embed(title: str, headers: tuple, rows: list, description: str = '', mark_rows: bool = True, timestamp: datetime = Embed.Empty):
    embed = Embed(title=title, description=description, color=COLOR_DEFAULT, timestamp=timestamp)
    num_fields = len(headers)
    field_values = ['' for i in range(num_fields)]

    if description:
        embed.add_field(name="** **", value="** **", inline=False)

    if len(rows) == 0:
        for i in range(num_fields):
            embed.add_field(name=headers[i], value="✖️*None yet!*")
        return embed

    for r in range(len(rows)):
        row = rows[r]
        if len(row) != num_fields:
            print(f'Invalid number of items in row: expected {num_fields} but found {len(row)}.')
            return None
        for i in range(num_fields):
            if mark_rows:
                field_values[i] += f"{'🟪' if r % 2 == 0 else '⬜'} "
            field_values[i] += f'{row[i]}\n'

    for i in range(num_fields):
        embed.add_field(name=headers[i], value=field_values[i])

    return embed


def replace_default_prefix(old_dict: dict, custom_prefix: str):
    new_dict = {}
    for key, value in old_dict.items():
        if isinstance(value, dict):
            value = replace_default_prefix(value, custom_prefix)
        elif isinstance(value, list):
            value = [replace_default_prefix(item, custom_prefix) for item in value]  # This assumes all items are dicts.
        elif isinstance(value, str):
            value = value.replace(DEFAULT_PREFIX, custom_prefix)
        new_dict[key] = value
    return new_dict
