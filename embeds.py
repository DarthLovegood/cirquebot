import discord

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


def create_basic_embed(description: str, emoji: str = None):
    if emoji:
        description = FORMAT_EMOJI_TEXT.format(emoji, description)
    return discord.Embed(description=description, color=COLOR_DEFAULT)


def create_help_embed(help_dict: dict):
    title = FORMAT_HELP_TITLE.format(help_dict[KEY_COMMAND])
    embed = discord.Embed(title=title, description=help_dict[KEY_DESCRIPTION], color=COLOR_DEFAULT)

    for command in help_dict[KEY_SUBCOMMANDS]:
        emoji = command[KEY_EMOJI]
        title = FORMAT_COMMAND_TITLE.format(emoji, command[KEY_TITLE].replace('[', '*[').replace(']', ']*'))
        description = f'{command[KEY_DESCRIPTION]}\n**Example:** `{command[KEY_EXAMPLE]}`'
        embed.add_field(name=title, value=description, inline=False)

    return embed


def create_table_embed(title: str, headers: tuple, rows: list):
    embed = discord.Embed(title=title, color=COLOR_DEFAULT)
    num_fields = len(headers)
    field_values = ['' for i in range(num_fields)]

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
            emoji = "🟪" if r % 2 == 0 else "⬜"
            field_values[i] += f'{emoji} {row[i]}\n'

    for i in range(num_fields):
        embed.add_field(name=headers[i], value=field_values[i])

    return embed


def create_event_embed(event: dict):
    # TODO: Implement!
    print(str(event))
    pass
