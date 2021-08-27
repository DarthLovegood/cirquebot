import aiofiles.os
import asyncio
import io
import re
import sqlite3
from discord.ext import commands
from json import dumps, loads
from lib import ocr, utils
from lib.embeds import *
from lib.prefixes import get_prefix

EMOJI_SESSION_NEXT = '▶'
EMOJI_SESSION_COMPLETED = '🥳'
EMOJI_SESSION_CANCELED = '💩'

FILENAME_IMAGE = 'image_with_bounds.png'
FILENAME_SESSION = 'clownquest_session.csv'

TABLE_HEADERS = ('🧑 Character Name', '👪 Legacy Name', '🏆 Conquest Points')

TEXT_FORMAT_BOUNDS = 'Current bounds for **{0}**:\n```json\n{1}\n```'  # args: user name, json text
TEXT_ONE_IMAGE = 'Please attach/embed exactly one image.'
TEXT_SESSION_CONFIRMATION = f'React with {EMOJI_SUCCESS} to accept this result or {EMOJI_ERROR} to reject it.'
TEXT_SESSION_MENU = '\n\nPlease react with one of the following emoji: ' \
                    f'\n \u200B \u200B \u200B {EMOJI_SESSION_NEXT} = Process another image' \
                    f'\n \u200B \u200B \u200B {EMOJI_SESSION_COMPLETED} = Finish the session and export all data' \
                    f'\n \u200B \u200B \u200B {EMOJI_SESSION_CANCELED} = Scrap the current session and discard all data'
TEXT_SESSION_TIMEOUT = 'You were too slow! \u200B \u200B 🦥 \u200B Canceled the OCR session and discarded its data.'

TIMEOUT_SECONDS = 60


class Clownquest(commands.Cog):
    db = 'data/clownquest.db'
    help = {
        KEY_TITLE: 'Clownquest',
        KEY_DESCRIPTION: 'Extracts conquest data from screenshots of the guild member list.',
        KEY_COMMAND: '!cb clownquest',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🔍',
                KEY_TITLE: 'demo [screenshot image]',
                KEY_DESCRIPTION: 'Demonstrates the OCR functionality on the given image.',
                KEY_EXAMPLE: '!cb cq demo <paste the screenshot image>'
            },
            {
                KEY_EMOJI: '📐',
                KEY_TITLE: 'showbounds [screenshot image]',
                KEY_DESCRIPTION: 'Displays boundaries over the given image, and provides a template for editing them.',
                KEY_EXAMPLE: '!cb cq showbounds <paste the screenshot image>'
            },
            {
                KEY_EMOJI: '📝',
                KEY_TITLE: 'setbounds [message link]',
                KEY_DESCRIPTION: 'Sets your custom boundaries based on the given template message.',
                KEY_EXAMPLE: '!cb cq setbounds https://discord.com/URL'
            },
            {
                KEY_EMOJI: EMOJI_SESSION_NEXT,
                KEY_TITLE: 'start',
                KEY_DESCRIPTION: 'Starts a new session in which data from a series of images is saved to a file.',
                KEY_EXAMPLE: '!cb cq start'
            },
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        with sqlite3.connect(self.db) as connection:
            c = connection.cursor()
            c.execute(
                '''CREATE TABLE IF NOT EXISTS `bounds` (
                    `id` INTEGER PRIMARY KEY UNIQUE,
                    `bounds` TEXT NOT NULL
                );''')
            connection.commit()
            c.close()

    @commands.command(aliases=['conquest', 'conq', 'cq'])
    async def clownquest(self, ctx, command: str = None, *args):
        message = ctx.message
        if self.bot.get_cog('CQSession'):
            return  # Message will be handled by the active CQSession.
        elif command == 'demo' and len(args) <= 1:
            image_data = await utils.get_attachment_data(message) if not args else await utils.get_embed_data(message)
            await self.demo(ctx, image_data)
        elif command == 'showbounds' and len(args) <= 1:
            image_data = await utils.get_attachment_data(message) if not args else await utils.get_embed_data(message)
            await self.show_bounds(ctx, image_data)
        elif command == 'setbounds' and len(args) == 1:
            await self.set_bounds(ctx, args[0])
        elif command == 'start' and len(args) == 0:
            await self.start(ctx)
        else:
            prefix = get_prefix(self.bot, ctx.message)
            await ctx.send(embed=create_help_embed(self.help, prefix))

    @staticmethod
    def get_bounds_for_user(db, user_id):
        bounds = ocr.DEFAULT_BOUNDS
        with sqlite3.connect(db) as connection:
            c = connection.cursor()
            c.execute('SELECT * FROM bounds WHERE id=?', (user_id,))
            row = c.fetchone()
            if row:
                bounds = loads(row[1])
            c.close()
        return bounds

    async def demo(self, ctx, image_data):
        if image_data:
            async with ctx.message.channel.typing():
                bounds = Clownquest.get_bounds_for_user(self.db, ctx.author.id)
                rows = ocr.process_screenshot(io.BytesIO(image_data), bounds)
            await ctx.send(embed=create_table_embed('', TABLE_HEADERS, rows))
        else:
            await ctx.send(embed=create_basic_embed(TEXT_ONE_IMAGE, EMOJI_ERROR))

    async def show_bounds(self, ctx, image_data):
        if image_data:
            async with ctx.message.channel.typing():
                bounds = Clownquest.get_bounds_for_user(self.db, ctx.author.id)
                ocr.draw_bounds(io.BytesIO(image_data), FILENAME_IMAGE, bounds)
            embed_text = TEXT_FORMAT_BOUNDS.format(ctx.author.display_name, dumps(bounds, indent=2))
            await ctx.send(file=discord.File(FILENAME_IMAGE))
            await ctx.send(embed=create_basic_embed(embed_text, EMOJI_INFO))
            await aiofiles.os.remove(FILENAME_IMAGE)
        else:
            await ctx.send(embed=create_basic_embed(TEXT_ONE_IMAGE, EMOJI_ERROR))

    async def set_bounds(self, ctx, message_link):
        bounds = await utils.fetch_dict_from_message(
            ctx, message_link, required_keys=ocr.DEFAULT_BOUNDS.keys(), enforce_numeric_values=True)
        if bounds:
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM bounds WHERE id=?', (ctx.author.id,))
                if c.fetchone():
                    c.execute('UPDATE bounds SET bounds=? WHERE id=?', (dumps(bounds), ctx.author.id))
                    embed_msg = f'Updated custom bounds for **{ctx.author.display_name}**.'
                else:
                    c.execute('INSERT INTO bounds VALUES (?, ?)', (ctx.author.id, dumps(bounds)))
                    embed_msg = f'Added custom bounds for **{ctx.author.display_name}**.'
                c.close()
            await ctx.send(embed=create_basic_embed(embed_msg, EMOJI_SUCCESS))

    async def start(self, ctx):
        session_cog = Clownquest.CQSession(self.bot, self.db, ctx)
        self.bot.add_cog(session_cog)
        await session_cog.prompt_for_message(is_first_message=True)

    class CQSession(commands.Cog):
        def __init__(self, bot, db, ctx):
            self.bot = bot
            self.db = db
            self.owner = ctx.author
            self.channel = ctx.channel
            self.expected_emoji = []
            self.messages_to_delete = set()

        def check_message(self, message):
            return message.author.id == self.owner.id and message.channel.id == self.channel.id

        def check_reaction(self, reaction, user):
            return user.id == self.owner.id and str(reaction.emoji) in self.expected_emoji

        @commands.Cog.listener()
        async def on_message(self, message):
            if self.check_message(message) and self.expected_emoji:
                embed_text = f'{message.author.mention}, please react to my message above!'
                info_message = await message.channel.send(embed=create_basic_embed(embed_text, EMOJI_WARNING))
                self.messages_to_delete.update({info_message, message})

        async def prompt_for_message(self, is_first_message=False):
            embed_text = f'OCR session in progress! {TEXT_ONE_IMAGE}'
            if is_first_message:
                embed_text = embed_text[:-1] + ' per message.'
            prompt_message = await self.channel.send(embed=create_basic_embed(embed_text, EMOJI_SESSION_NEXT))

            try:
                message = await self.bot.wait_for('message', timeout=TIMEOUT_SECONDS, check=self.check_message)
            except asyncio.TimeoutError:
                if not is_first_message:
                    self.messages_to_delete.update({prompt_message})
                await self.finish(create_basic_embed(TEXT_SESSION_TIMEOUT, EMOJI_ERROR))
            else:
                if not is_first_message:
                    await prompt_message.delete()
                await self.handle_session_message(message)

        async def prompt_for_reaction(self, embed, callback, *emoji_options):
            prompt_message = await self.channel.send(embed=embed)
            self.expected_emoji = list(emoji_options)
            for emoji in emoji_options:
                await prompt_message.add_reaction(emoji)

            try:
                reaction, unused_user = \
                    await self.bot.wait_for('reaction_add', timeout=TIMEOUT_SECONDS, check=self.check_reaction)
            except asyncio.TimeoutError:
                self.messages_to_delete.update({prompt_message})
                await self.finish(create_basic_embed(TEXT_SESSION_TIMEOUT, EMOJI_ERROR))
            else:
                self.expected_emoji.clear()
                await prompt_message.clear_reactions()
                await callback(str(reaction), prompt_message)

        async def handle_session_message(self, message):
            async with message.channel.typing():
                image_data = await utils.get_attachment_data(message) or await utils.get_embed_data(message)

            if not image_data:
                embed = create_basic_embed('Message didn\'t contain a single image.', EMOJI_ERROR)
                info_message = await message.channel.send(embed=embed)
                self.messages_to_delete.update({info_message, message})
                await self.prompt_for_message()
                return

            async with message.channel.typing():
                bounds = Clownquest.get_bounds_for_user(self.db, message.author.id)
                rows = ocr.process_screenshot(io.BytesIO(image_data), bounds)
                embed = create_table_embed(TEXT_SESSION_CONFIRMATION, TABLE_HEADERS, rows)

            async def confirmation_callback(emoji, prompt_message):
                if emoji == EMOJI_SUCCESS:
                    embed_text = 'Saved data for members ' \
                                 f'**{rows[0][0]} ({rows[0][1]})** to **{rows[-1][0]} ({rows[-1][1]})**.'
                    async with aiofiles.open(FILENAME_SESSION, 'a') as output_file:
                        output_text = '\n'.join(re.sub('[\'"], [\'"]?', ',', str(row)[2:-1]) for row in rows) + '\n'
                        await output_file.write(output_text)
                else:
                    embed_text = 'Scrapping OCR data for above image.'
                await prompt_message.edit(embed=create_basic_embed(embed_text, emoji))
                await self.prompt_for_reaction(create_basic_embed(TEXT_SESSION_MENU), self.next_step_callback,
                                               EMOJI_SESSION_NEXT, EMOJI_SESSION_COMPLETED, EMOJI_SESSION_CANCELED)

            await self.prompt_for_reaction(embed, confirmation_callback, EMOJI_SUCCESS, EMOJI_ERROR)

        async def next_step_callback(self, emoji, prompt_message):
            if emoji == EMOJI_SESSION_NEXT:
                await prompt_message.delete()
                await self.prompt_for_message()
                return

            if emoji == EMOJI_SESSION_COMPLETED:
                embed_text = 'Successfully completed the OCR session! Here\'s a file containing all the data.'
                file = discord.File(FILENAME_SESSION)
            else:
                embed_text = 'Canceled the OCR session. All of its data has been discarded.'
                file = None

            self.messages_to_delete.update({prompt_message})
            await self.finish(create_basic_embed(embed_text, emoji), file)

        async def finish(self, embed, file=None):
            await self.channel.delete_messages(self.messages_to_delete)
            await self.channel.send(embed=embed)

            self.messages_to_delete.clear()
            self.expected_emoji.clear()
            self.bot.remove_cog('CQSession')

            if file:
                await self.channel.send(file=file)
                file.close()
                await aiofiles.os.remove(FILENAME_SESSION)


def setup(bot):
    bot.add_cog(Clownquest(bot))
