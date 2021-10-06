from asyncio import Lock
from datetime import datetime, timedelta, timezone
from discord import File
from discord.ext import commands
from lib.embeds import create_basic_embed

KEY_TIMESTAMP = 'timestamp'  # type: datetime
KEY_CHANNEL_ID = 'channel_id'  # type: int
KEY_AUTHOR = 'author'  # type: Member
KEY_MESSAGE_TEXT = 'message_text'  # type: str
KEY_ATTACHMENTS = 'attachments'  # type: list[Attachment]

SNIPE_WINDOW = timedelta(seconds=30)

TEXT_SNIPER_FAIL = '**"SNIPER, NO SNIPING!"**\n*"Oh, mannnn...*"'


class Sniper(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.deleted_message_cache = []
        self.edited_message_cache = []
        self.deleted_message_cache_lock = Lock()
        self.edited_message_cache_lock = Lock()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.author.bot:
            await Sniper.add_to_cache(message, self.deleted_message_cache, self.deleted_message_cache_lock)

    @commands.Cog.listener()
    async def on_message_edit(self, original_message, edited_message):
        if (not original_message.author.bot) and (original_message.content != edited_message.content):
            await Sniper.add_to_cache(original_message, self.edited_message_cache, self.edited_message_cache_lock)

    @commands.command()
    async def snipe(self, ctx):
        await Sniper.attempt_snipe(ctx.channel, self.deleted_message_cache, self.deleted_message_cache_lock)

    @commands.command(aliases=['esnipe'])
    async def editsnipe(self, ctx):
        await Sniper.attempt_snipe(ctx.channel, self.edited_message_cache, self.edited_message_cache_lock)

    @staticmethod
    async def add_to_cache(message, message_cache, message_cache_lock):
        timestamp = datetime.now(timezone.utc)
        async with message_cache_lock:
            message_cache.append({
                KEY_TIMESTAMP: timestamp,
                KEY_CHANNEL_ID: message.channel.id,
                KEY_AUTHOR: message.author,
                KEY_MESSAGE_TEXT: message.content,
                KEY_ATTACHMENTS: message.attachments
            })

    @staticmethod
    async def attempt_snipe(channel, message_cache, message_cache_lock):
        sniped_user = None
        sniped_messages = []
        sniped_attachments = []
        sniped_at = datetime.now(timezone.utc)
        snipe_threshold = sniped_at - SNIPE_WINDOW

        async with message_cache_lock:
            # Remove messages in the cache that were deleted too long ago to be sniped (i.e. outside the snipe window).
            while message_cache and (message_cache[0][KEY_TIMESTAMP] < snipe_threshold):
                message_cache.pop(0)

            # Identify the first user who deleted their messages in the current channel within the snipe window, and
            # capture ALL deleted messages within the snipe window by that same user in the current channel.
            cache_index = 0
            while cache_index < len(message_cache):
                cache_entry = message_cache[cache_index]
                if cache_entry[KEY_CHANNEL_ID] == channel.id:
                    if not sniped_user:
                        sniped_user = cache_entry[KEY_AUTHOR]
                    if cache_entry[KEY_AUTHOR].id == sniped_user.id:
                        sniped_messages.append(cache_entry[KEY_MESSAGE_TEXT])
                        sniped_attachments += cache_entry[KEY_ATTACHMENTS]
                        message_cache.pop(cache_index)
                        continue  # Continue without incrementing the index because we removed the current entry.
                cache_index += 1

        await Sniper.send_snipe_response(channel, sniped_user, sniped_messages, sniped_attachments, sniped_at)

    @staticmethod
    async def send_snipe_response(channel, user, messages, attachments, timestamp):
        if user and messages:
            embed = create_basic_embed('\n'.join(messages))
            embed.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)
            embed.timestamp = timestamp
            if (len(attachments) == 1) and ('image' in attachments[0].content_type):
                embed.set_image(url=attachments[0].url)
            await channel.send(embed=embed)
        else:
            embed = create_basic_embed(TEXT_SNIPER_FAIL)
            file = File('assets/swiper.png', 'image.png')
            embed.set_thumbnail(url='attachment://image.png')
            await channel.send(embed=embed, file=file)


def setup(bot):
    bot.add_cog(Sniper(bot))
