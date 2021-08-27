from discord import FFmpegPCMAudio
from discord.ext import commands
from lib.embeds import create_basic_embed, EMOJI_ERROR, EMOJI_SUCCESS
from youtube_dl import YoutubeDL

TEXT_SUCCESS_FORMAT = '{0} \u200B \u200B Now playing **{1}** in **{2}**!'  # args: emoji, title, channel name

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
}


class AudioPlayer(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def babyshark(self, ctx):
        audio_emoji = '🦈'
        audio_title = 'Baby Shark'
        audio_url = 'https://www.youtube.com/watch?v=LBHYhvOHgvc'
        await self.handle_audio_command(ctx, audio_emoji, audio_title, audio_url)

    @commands.command()
    async def bingbangbong(self, ctx):
        audio_emoji = '💃'
        audio_title = 'UK Hun?'
        audio_url = 'https://www.youtube.com/watch?v=z9wRiNzM6Ww'
        await self.handle_audio_command(ctx, audio_emoji, audio_title, audio_url)

    @commands.command()
    async def nyancat(self, ctx):
        audio_emoji = '🐱'
        audio_title = 'Nyan Cat'
        audio_url = 'https://www.youtube.com/watch?v=QH2-TGUlwu4'
        await self.handle_audio_command(ctx, audio_emoji, audio_title, audio_url)

    @commands.command()
    async def rickroll(self, ctx):
        audio_emoji = '🕺'
        audio_title = 'Never Gonna Give You Up'
        audio_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        await self.handle_audio_command(ctx, audio_emoji, audio_title, audio_url)

    @commands.command()
    async def stopaudio(self, ctx):
        await self.disconnect_voice_clients()
        await ctx.channel.send(embed=create_basic_embed('Successfully stopped all audio playback.', EMOJI_SUCCESS))

    async def handle_audio_command(self, ctx, audio_emoji, audio_title, audio_url):
        text_channel = ctx.channel
        if len(ctx.message.mentions) == 1:
            user = ctx.message.mentions[0]
            if user.voice:
                voice_channel = user.voice.channel
                success_text = TEXT_SUCCESS_FORMAT.format(audio_emoji, audio_title, voice_channel.name)
                async with text_channel.typing():
                    await self.disconnect_voice_clients()
                    await self.play_youtube_audio(voice_channel, text_channel, audio_url, success_text)
            else:
                embed = create_basic_embed(f'**{user.mention}** is not currently in a voice channel.', EMOJI_ERROR)
                await text_channel.send(embed=embed)
        else:
            embed = create_basic_embed('Please specify exactly one person to receive the audio.', EMOJI_ERROR)
            await text_channel.send(embed=embed)

    async def play_youtube_audio(self, voice_channel, text_channel, url, success_text):
        # noinspection PyBroadException
        try:
            loop = self.bot.loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: YoutubeDL(YTDL_OPTIONS).extract_info(url, download=False))
            audio_source = FFmpegPCMAudio(data['url'])
            voice_client = await voice_channel.connect()
            voice_client.play(audio_source)
            await text_channel.send(embed=create_basic_embed(success_text))
        except Exception as exception:
            print(exception)
            await text_channel.send(embed=create_basic_embed('Error playing YouTube audio.', EMOJI_ERROR))

    async def disconnect_voice_clients(self):
        for voice_client in self.bot.voice_clients:
            await voice_client.disconnect()


def setup(bot):
    bot.add_cog(AudioPlayer(bot))
