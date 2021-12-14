from asyncio import Lock
from datetime import datetime, timedelta, timezone
from discord import HTTPException
from discord.ext import commands
from lib.embeds import create_authored_embed, create_basic_embed
from lib.utils import get_message_link_string

KEY_TIMESTAMP = 'timestamp'  # type: datetime
KEY_CHANNEL_ID = 'channel_id'  # type: int
KEY_USER = 'user'  # type: Member
KEY_CONTENT = 'content'  # type: str
KEY_EXTRAS = 'extras'  # type: str or list[Attachment]

SNIPE_WINDOW = timedelta(seconds=30)

TEXT_SNIPER_FAIL = '**"SNIPER, NO SNIPING!"**\n*"Oh, mannnn...*"'
TEXT_SENT_FILE = '*Sent a file!*'
TEXT_SENT_FILES = '*Sent some files!*'

URL_SNIPER_ICON = 'https://cdn.discordapp.com/attachments/919924341343399966/919934086183813120/sniper.png'
URL_SWIPER_ICON = 'https://cdn.discordapp.com/attachments/919924341343399966/919933002270789653/swiper.png'


class Sniper(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.deleted_message_cache = []
        self.deleted_message_cache_lock = Lock()
        self.edited_message_cache = []
        self.edited_message_cache_lock = Lock()
        self.removed_reaction_cache = []
        self.removed_reaction_cache_lock = Lock()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.author.bot:
            await Sniper.add_to_cache(self.deleted_message_cache, self.deleted_message_cache_lock,
                                      channel=message.channel,
                                      user=message.author,
                                      content=message.content,
                                      extras=message.attachments)

    @commands.Cog.listener()
    async def on_message_edit(self, original_message, edited_message):
        changed_content = original_message.content != edited_message.content
        removed_attachments = [a for a in original_message.attachments if a not in edited_message.attachments]
        if (not original_message.author.bot) and (changed_content or removed_attachments):
            await Sniper.add_to_cache(self.edited_message_cache, self.edited_message_cache_lock,
                                      channel=original_message.channel,
                                      user=original_message.author,
                                      content=original_message.content,  # TODO: Display the text diff more clearly.
                                      extras=removed_attachments)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if not user.bot:
            await Sniper.add_to_cache(self.removed_reaction_cache, self.removed_reaction_cache_lock,
                                      channel=reaction.message.channel,
                                      user=user,
                                      content=reaction.emoji,
                                      extras=reaction.message.jump_url)

    @commands.command()
    async def snipe(self, ctx):
        await Sniper.attempt_snipe(
            ctx.channel, self.deleted_message_cache, self.deleted_message_cache_lock, Sniper.send_snipe_response)

    @commands.command(aliases=['esnipe'])
    async def editsnipe(self, ctx):
        await Sniper.attempt_snipe(
            ctx.channel, self.edited_message_cache, self.edited_message_cache_lock, Sniper.send_snipe_response)

    @commands.command(aliases=['rsnipe'])
    async def reactsnipe(self, ctx):
        await Sniper.attempt_snipe(
            ctx.channel, self.removed_reaction_cache, self.removed_reaction_cache_lock, Sniper.send_rsnipe_response)

    @staticmethod
    async def add_to_cache(cache, cache_lock, channel=None, user=None, content=None, extras=None):
        timestamp = datetime.now(timezone.utc)
        async with cache_lock:
            cache.append({
                KEY_TIMESTAMP: timestamp,
                KEY_CHANNEL_ID: channel.id,
                KEY_USER: user,
                KEY_CONTENT: content,
                KEY_EXTRAS: extras
            })

    @staticmethod
    async def attempt_snipe(channel, message_cache, message_cache_lock, success_callback):
        sniped_user = None
        sniped_content = []
        sniped_extras = []
        sniped_at = datetime.now(timezone.utc)
        snipe_threshold = sniped_at - SNIPE_WINDOW

        async with message_cache_lock:
            # Remove messages in the cache that were deleted too long ago to be sniped (i.e. outside the snipe window).
            while message_cache and (message_cache[0][KEY_TIMESTAMP] < snipe_threshold):
                message_cache.pop(0)

            # Identify the first user who deleted their messages/reactions in the current channel within the
            # snipe window, and capture ALL deleted messages/reactions within the snipe window by that same user
            # in the current channel.
            cache_index = 0
            while cache_index < len(message_cache):
                cache_entry = message_cache[cache_index]
                if cache_entry[KEY_CHANNEL_ID] == channel.id:
                    # Lock onto a target user if one hasn't already been chosen.
                    if not sniped_user:
                        sniped_user = cache_entry[KEY_USER]
                    # Snipe the message/reaction if it came from the target user.
                    if cache_entry[KEY_USER].id == sniped_user.id:
                        sniped_content.append(cache_entry[KEY_CONTENT])
                        if isinstance(cache_entry[KEY_EXTRAS], list):
                            sniped_extras += cache_entry[KEY_EXTRAS]
                        else:
                            sniped_extras.append(cache_entry[KEY_EXTRAS])
                        message_cache.pop(cache_index)
                        continue  # Continue without incrementing the index because we removed the current entry.
                cache_index += 1

        if sniped_user and sniped_content:
            await success_callback(channel, sniped_user, sniped_content, sniped_extras, sniped_at)
        else:
            await Sniper.send_failure_response(channel)

    @staticmethod
    async def send_failure_response(channel):
        embed = create_basic_embed(TEXT_SNIPER_FAIL)
        embed.set_thumbnail(url=URL_SWIPER_ICON)
        await channel.send(embed=embed)

    @staticmethod
    async def send_rsnipe_response(channel, user, emojis, message_urls, timestamp):
        # TODO: Handle long emoji lists better. Currently, this will send a separate message for every emoji.
        for i, emoji in enumerate(emojis):
            message_link_string = f'**{get_message_link_string(message_urls[i])}**'
            embed = create_basic_embed(f'Message: {message_link_string}', timestamp=timestamp)

            if isinstance(emoji, str):
                embed.set_author(name=f'{emoji} {user.name}#{user.discriminator}')
            else:
                embed.set_author(name=f'{user.name}#{user.discriminator} with :{emoji.name}:', icon_url=emoji.url)

            await channel.send(embed=embed)

    @staticmethod
    async def send_snipe_response(channel, user, messages, attachments, timestamp):
        embed = create_authored_embed(user, timestamp, '\n'.join(messages).strip())
        file = None

        if attachments and Sniper.is_image(attachments[0]):
            file = await Sniper.attach_image_file(channel, embed, attachments[0])
            attachments.pop(0)

        if not attachments:
            await channel.send(embed=embed, file=file)
            return

        if (not embed.description) and any(not Sniper.is_image(attachment) for attachment in attachments):
            embed.description = TEXT_SENT_FILE if len(attachments) == 1 else TEXT_SENT_FILES

        await channel.send(embed=embed, file=file)

        for attachment in attachments:
            if Sniper.is_image(attachment):
                embed = create_authored_embed(user, timestamp)
                file = await Sniper.attach_image_file(channel, embed, attachment)
                await channel.send(embed=embed, file=file)
            else:
                async with channel.typing():
                    try:
                        file = await attachment.to_file(use_cached=True)
                        await channel.send(file=file)
                    except HTTPException:
                        embed = create_authored_embed(user, timestamp, f'**{attachment.proxy_url}**')
                        await channel.send(embed=embed)

    @staticmethod
    async def attach_image_file(channel, embed, attachment):
        async with channel.typing():
            file = await attachment.to_file(use_cached=True)
            embed.set_image(url=f'attachment://{file.filename}')
        return file

    @staticmethod
    def is_image(attachment):
        return 'image' in attachment.content_type


def setup(bot):
    bot.add_cog(Sniper(bot))
