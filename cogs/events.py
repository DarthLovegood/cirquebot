import sqlite3
from discord.ext import commands
from lib.embeds import *
from lib.event import Event
from lib.prefixes import get_prefix

FORMAT_JSON = '```json\n{0}```'


class Events(commands.Cog):
    db = 'data/events.db'
    help = {
        KEY_EMOJI: '📆',
        KEY_TITLE: 'Events',
        KEY_DESCRIPTION: 'Manages dynamic sign-up sheets for custom guild events.',
        KEY_COMMAND: '!cb events',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '📐',
                KEY_TITLE: 'template',
                KEY_DESCRIPTION: 'Provides a template that can be used to create a new event.',
                KEY_EXAMPLE: '!cb ev template'
            },
            {
                KEY_EMOJI: '📄',
                KEY_TITLE: 'create [message link]',
                KEY_DESCRIPTION: 'Creates a new event from the given template message.',
                KEY_EXAMPLE: '!cb ev create https://discord.com/URL'
            },
            {
                KEY_EMOJI: '📝',
                KEY_TITLE: 'edit [message link]',
                KEY_DESCRIPTION: 'Starts the editing process for the event in the given message.',
                KEY_EXAMPLE: '!cb ev edit https://discord.com/URL'
            },
            {
                KEY_EMOJI: '📨',
                KEY_TITLE: 'copy [message link] [channel]',
                KEY_DESCRIPTION: 'Copies the event in the given message to the given channel.',
                KEY_EXAMPLE: '!cb ev copy https://discord.com/URL #event-signups'
            },
            {
                KEY_EMOJI: '🔓',
                KEY_TITLE: 'open [message link]',
                KEY_DESCRIPTION: 'Opens sign-ups for the event in the given message.',
                KEY_EXAMPLE: '!cb ev open https://discord.com/URL'
            },
            {
                KEY_EMOJI: '🔒',
                KEY_TITLE: 'close [message link]',
                KEY_DESCRIPTION: 'Closes sign-ups for the event in the given message.',
                KEY_EXAMPLE: '!cb ev close https://discord.com/URL'
            },
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        with sqlite3.connect(self.db) as connection:
            # TODO: Use a database to store events.
            pass

    @commands.command(aliases=['event', 'ev'])
    async def events(self, ctx, command: str = None, *args):
        if command == 'template' and len(args) == 0:
            await ctx.send(FORMAT_JSON.format(Event().to_json()))
        elif command == 'create' and len(args) == 1:
            await self.create_event(ctx, args[0])
        elif command == 'new' and len(args) == 0:
            # TODO: Document and implement this - interactive event creation session.
            pass
        elif command == 'edit' and len(args) == 1:
            pass
        elif command == 'copy' and len(args) == 2:
            pass
        elif command == 'open' and len(args) == 1:
            pass
        elif command == 'close' and len(args) == 1:
            pass
        else:
            prefix = get_prefix(self.bot, ctx.message)
            await ctx.send(embed=create_help_embed(self.help, prefix))

    @staticmethod
    async def create_event(ctx, template_msg_link):
        split_link = template_msg_link.split("/")
        channel_id = int(split_link[-2])
        message_id = int(split_link[-1])
        message = await ctx.bot.get_channel(channel_id).fetch_message(message_id)
        content = message.content
        event_or_error_message = Event.from_json(ctx, content[content.index("{"):content.rindex("}") + 1])

        if isinstance(event_or_error_message, Event):
            event = event_or_error_message
            await ctx.send(FORMAT_JSON.format(event.to_json()))
        elif isinstance(event_or_error_message, str):
            error_message = event_or_error_message
            await ctx.send(embed=create_basic_embed(error_message, EMOJI_ERROR))


def setup(bot):
    bot.add_cog(Events(bot))
