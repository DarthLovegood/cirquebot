import asyncio
import re
from io import BytesIO

from PIL import Image
from discord import File, FFmpegPCMAudio
from discord.ext import commands
from youtube_dl import YoutubeDL

from lib.embeds import EMOJI_ERROR, EMOJI_SUCCESS, create_basic_embed

FILENAME_BONK = 'assets/bonk.png'
FILENAME_MASK = 'assets/mask.png'
FILENAME_SUNDER = 'assets/sunder.png'
FILENAME_SPANK_1 = 'assets/spank1.png'
FILENAME_SPANK_2 = 'assets/spank2.png'
FILENAME_THERON = 'assets/theron.png'

REGEX_BABY_SHARK = re.compile(r'^\s*/babyshark(\s*<@!?[0-9]*>)*\s*$', re.IGNORECASE)
REGEX_BING_BANG_BONG = re.compile(r'^\s*/bingbangbong(\s*<@!?[0-9]*>)*\s*$', re.IGNORECASE)
REGEX_BONK = re.compile(r'^\s*/(sunder)?bonk(\s*<@!?[0-9]*>)*\s*$', re.IGNORECASE)
REGEX_NYAN_CAT = re.compile(r'^\s*/nyancat(\s*<@!?[0-9]*>)*\s*$', re.IGNORECASE)
REGEX_QWEPHESS = re.compile(r'^(.*?(\bkephess\b)[^$]*)$', re.IGNORECASE)
REGEX_RICK_ROLL = re.compile(r'^\s*/rickroll(\s*<@!?[0-9]*>)*\s*$', re.IGNORECASE)
REGEX_SPANK = re.compile(r'^\s*/spank((\s*theron)|(\s*<@!?[0-9]*>)*)\s*$', re.IGNORECASE)
REGEX_SPANK_EMOJI = re.compile(r'^\s*(<:spank[a-z]*:740455662856831007>\s*)+$', re.IGNORECASE)
REGEX_STOP_AUDIO = re.compile(r'^\s*/stopaudio\s*$', re.IGNORECASE)

TEXT_BABY_SHARK = '🦈 \u200B \u200B Now playing **Baby Shark** in **{0}**!'
TEXT_BING_BANG_BONG = '💃 \u200B \u200B Now playing **UK Hun?** in **{0}**!'
TEXT_NYAN_CAT = '🐱 \u200B \u200B Now playing **Nyan Cat** in **{0}**!'
TEXT_RICK_ROLL = '🕺 \u200B \u200B Now playing **Never Gonna Give You Up** in **{0}**!'

URL_BABY_SHARK = 'https://www.youtube.com/watch?v=LBHYhvOHgvc'
URL_BING_BANG_BONG = 'https://www.youtube.com/watch?v=z9wRiNzM6Ww'
URL_NYAN_CAT = 'https://www.youtube.com/watch?v=QH2-TGUlwu4'
URL_RICK_ROLL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
}


class EasterEggs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return
        elif REGEX_BABY_SHARK.match(message.content) and len(message.mentions) == 1:
            await EasterEggs.play_youtube_audio(
                self.bot, message.mentions[0], message.channel, URL_BABY_SHARK, TEXT_BABY_SHARK)
        elif REGEX_BING_BANG_BONG.match(message.content) and len(message.mentions) == 1:
            await EasterEggs.play_youtube_audio(
                self.bot, message.mentions[0], message.channel, URL_BING_BANG_BONG, TEXT_BING_BANG_BONG)
        elif REGEX_BONK.match(message.content) and len(message.mentions) == 1:
            sunder = 'sunder' in message.content.lower()
            await EasterEggs.bonk(message.channel, message.author, message.mentions[0], sunder=sunder)
        elif REGEX_NYAN_CAT.match(message.content) and len(message.mentions) == 1:
            await EasterEggs.play_youtube_audio(
                self.bot, message.mentions[0], message.channel, URL_NYAN_CAT, TEXT_NYAN_CAT)
        elif REGEX_QWEPHESS.match(message.content):
            await EasterEggs.correctQwephess(message.channel, message)
        elif REGEX_RICK_ROLL.match(message.content) and len(message.mentions) == 1:
            await EasterEggs.play_youtube_audio(
                self.bot, message.mentions[0], message.channel, URL_RICK_ROLL, TEXT_RICK_ROLL)
        elif REGEX_SPANK.match(message.content):
            if 'theron' in message.content.lower() and len(message.mentions) == 0:
                await EasterEggs.spank(message.channel, message.author, None, True)
            elif len(message.mentions) == 1:
                await EasterEggs.spank(message.channel, message.author, message.mentions[0])
        elif REGEX_SPANK_EMOJI.match(message.content):
            await EasterEggs.spank(message.channel, self.bot.user, message.author)
        elif REGEX_STOP_AUDIO.match(message.content):
            await EasterEggs.stop_audio(self.bot, message.channel)

    @staticmethod
    async def play_youtube_audio(bot, target_user, text_channel, url, confirmation_text):
        # noinspection PyBroadException
        try:
            loop = bot.loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: YoutubeDL(YTDL_OPTIONS).extract_info(url, download=False))
            audio_source = FFmpegPCMAudio(data['url'])
            voice_client = await target_user.voice.channel.connect()
            voice_client.play(audio_source)
            await text_channel.send(embed=create_basic_embed(confirmation_text.format(target_user.voice.channel.name)))
        except Exception as exception:
            print(exception)
            await text_channel.send(embed=create_basic_embed('Error playing YouTube audio.', EMOJI_ERROR))

    @staticmethod
    async def stop_audio(bot, text_channel):
        for voice_client in bot.voice_clients:
            await voice_client.disconnect()
        await text_channel.send(embed=create_basic_embed('Successfully stopped all audio playback.', EMOJI_SUCCESS))

    @staticmethod
    async def bonk(channel, bonker, bonkee, sunder=False):
        async with channel.typing():
            bonk_image = Image.open(FILENAME_BONK)
            bonker_image = Image.open(FILENAME_SUNDER) if sunder else await EasterEggs.get_avatar_image(bonker)
            bonkee_image = await EasterEggs.get_avatar_image(bonkee)

            if bonker_image:
                bonk_image = EasterEggs.process_image(
                    bonker_image, new_size=(75, 75), apply_mask=True, bg_image=bonk_image, position=(42, 30))

            if bonkee_image:
                bonk_image = EasterEggs.process_image(
                    bonkee_image, new_size=(100, 32), rotate_angle=28, apply_mask=True,
                    bg_image=bonk_image, position=(270, 94))

        with BytesIO() as image_bytes:
            bonk_image.save(image_bytes, 'png')
            image_bytes.seek(0)
            await channel.send(file=File(fp=image_bytes, filename='bonk.png'))

    @staticmethod
    async def spank(channel, spanker, spankee, theron=False):
        async with channel.typing():
            spank_image_1 = Image.open(FILENAME_SPANK_1)
            spank_image_2 = Image.open(FILENAME_SPANK_2)
            spanker_image = await EasterEggs.get_avatar_image(spanker)
            spankee_image = Image.open(FILENAME_THERON) if theron else await EasterEggs.get_avatar_image(spankee)

            if spanker_image:
                spank_image_1 = EasterEggs.process_image(
                    spanker_image, new_size=(64, 64), apply_mask=True, bg_image=spank_image_1, position=(155, 75))
                spank_image_2 = EasterEggs.process_image(
                    spanker_image, new_size=(64, 64), apply_mask=True, bg_image=spank_image_2, position=(142, 75))

            if spankee_image:
                spank_image_1 = EasterEggs.process_image(
                    spankee_image, new_size=(50, 50), apply_mask=True, bg_image=spank_image_1, position=(146, 202))
                spank_image_2 = EasterEggs.process_image(
                    spankee_image, new_size=(50, 50), apply_mask=True, bg_image=spank_image_2, position=(141, 202))

        with BytesIO() as image_bytes:
            spank_image_1.save(image_bytes, 'gif', save_all=True, append_images=[spank_image_2], duration=180, loop=0)
            image_bytes.seek(0)
            await channel.send(file=File(fp=image_bytes, filename='spank.gif'))

    @staticmethod
    async def get_avatar_image(user):
        if user:
            asset = user.avatar_url_as(format='png', size=128)
            if asset:
                return Image.open(BytesIO(await asset.read()))
        return None
    
    @staticmethod
    async def correctQwephess(channel, message):
        async with channel.typing():
            message_blocks = re.split("kephess", message.content, flags=re.IGNORECASE)
            kephess_index = message.content.lower().find("kephess")
            kephess_string = message.content[kephess_index:(kephess_index + len("kephess"))]
            qw = "Qw" if kephess_string[0].isupper() else "qw"
            new_message = message_blocks[0] + f"~~{kephess_string}~~ {qw}{kephess_string[1:]}" + message_blocks[1]
            await message.reply(new_message, mention_author=False)


    @staticmethod
    def process_image(image, new_size=None, rotate_angle=0, apply_mask=False, bg_image=None, position=(0, 0)):
        if new_size:
            image = image.resize(new_size)

        if rotate_angle != 0:
            image = image.rotate(rotate_angle, expand=True)

        if apply_mask:
            mask_image = Image.open(FILENAME_MASK).convert('L')
            mask_image = EasterEggs.process_image(mask_image, new_size=new_size, rotate_angle=rotate_angle)
        else:
            mask_image = None

        if bg_image:
            new_bg_image = bg_image.copy()
            new_bg_image.paste(image, position, mask_image)
            return new_bg_image

        if mask_image:
            new_image = image.copy()
            new_image.putalpha(mask_image)
            return new_image

        return image


def setup(bot):
    bot.add_cog(EasterEggs(bot))
