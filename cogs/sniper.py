from asyncio import Lock
from datetime import datetime, timedelta, timezone
from discord import File
from discord.ext import commands
from lib.embeds import create_basic_embed

KEY_DELETED_AT = 'deleted_at'  # type: datetime
KEY_CHANNEL_ID = 'channel_id'  # type: int
KEY_AUTHOR = 'author'  # type: Member
KEY_MESSAGE_TEXT = 'message_text'  # type: str

SNIPE_WINDOW = timedelta(seconds=10)

TEXT_SNIPER_FAIL = '**"SNIPER, NO SNIPING!"**\n*"Oh, mannnn...*"'


class Sniper(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.message_cache = []
        self.message_cache_lock = Lock()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        deleted_at = datetime.now(timezone.utc)
        if not message.author.bot:
            async with self.message_cache_lock:
                self.message_cache.append({
                    KEY_DELETED_AT: deleted_at,
                    KEY_CHANNEL_ID: message.channel.id,
                    KEY_AUTHOR: message.author,
                    KEY_MESSAGE_TEXT: message.content
                })

    @commands.command()
    async def snipe(self, ctx):
        sniped_user = None
        sniped_messages = []
        sniped_at = datetime.now(timezone.utc)
        snipe_threshold = sniped_at - SNIPE_WINDOW

        async with self.message_cache_lock:
            # Remove messages in the cache that were deleted too long ago to be sniped (i.e. outside the snipe window).
            while self.message_cache and (self.message_cache[0][KEY_DELETED_AT] < snipe_threshold):
                self.message_cache.pop(0)

            # Identify the first user who deleted their messages in the current channel within the snipe window, and
            # capture ALL deleted messages within the snipe window by that same user in the current channel.
            cache_index = 0
            while cache_index < len(self.message_cache):
                cache_entry = self.message_cache[cache_index]
                if cache_entry[KEY_CHANNEL_ID] == ctx.channel.id:
                    if not sniped_user:
                        sniped_user = cache_entry[KEY_AUTHOR]
                    if cache_entry[KEY_AUTHOR].id == sniped_user.id:
                        sniped_messages.append(cache_entry[KEY_MESSAGE_TEXT])
                        self.message_cache.pop(cache_index)
                        continue  # Continue without incrementing the index because we removed the current entry.
                cache_index += 1

        await Sniper.send_snipe_response(ctx.channel, sniped_user, sniped_messages, sniped_at)

    @staticmethod
    async def send_snipe_response(ctx, user, messages, timestamp):
        if user and messages:
            embed = create_basic_embed('\n'.join(messages))
            embed.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)
            embed.timestamp = timestamp
            await ctx.send(embed=embed)
        else:
            embed = create_basic_embed(TEXT_SNIPER_FAIL)
            file = File('assets/swiper.png', 'image.png')
            embed.set_thumbnail(url='attachment://image.png')
            await ctx.send(embed=embed, file=file)


def setup(bot):
    bot.add_cog(Sniper(bot))
