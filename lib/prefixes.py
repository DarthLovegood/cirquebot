import json

DEFAULT_PREFIX = '!cb '
PREFIXES_PATH = 'data/prefixes.json'


def get_prefix(bot, message):
    if not message.guild:
        return DEFAULT_PREFIX
    with open(PREFIXES_PATH, 'r') as file:
        prefixes = json.load(file)
    server_id = str(message.guild.id)
    return prefixes.get(server_id, DEFAULT_PREFIX)
