import re
from io import BytesIO

from PIL import Image
from discord import File
from discord.ext import commands

from lib.embeds import create_basic_embed

FILENAME_BONK = 'assets/bonk.png'
FILENAME_MASK = 'assets/mask.png'

REGEX_BONK = re.compile(r'^\s*/bonk(\s*<@!?[0-9]*>)*\s*$')


class EasterEggs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return
        elif REGEX_BONK.match(message.content):
            if len(message.mentions) == 0:
                await EasterEggs.bonk(message.channel, message.author)
            elif len(message.mentions) == 1:
                await EasterEggs.bonk(message.channel, message.author, message.mentions[0])
            else:
                await message.channel.send(embed=create_basic_embed('I can only bonk one person at a time!', '😵'))

    @staticmethod
    async def bonk(channel, bonker, bonkee=None):
        async with channel.typing():
            bonk_image = Image.open(FILENAME_BONK)

            bonker_asset = bonker and bonker.avatar_url_as(format='png', size=128)
            bonkee_asset = bonkee and bonkee.avatar_url_as(format='png', size=128)

            if bonker_asset:
                bonker_image = Image.open(BytesIO(await bonker_asset.read()))
                bonk_image = EasterEggs.process_image(
                    bonker_image, new_size=(75, 75), apply_mask=True, bg_image=bonk_image, position=(42, 30))

            if bonkee_asset:
                bonkee_image = Image.open(BytesIO(await bonkee_asset.read()))
                bonk_image = EasterEggs.process_image(
                    bonkee_image, new_size=(100, 32), rotate_angle=28, apply_mask=True,
                    bg_image=bonk_image, position=(270, 94))

        with BytesIO() as image_bytes:
            bonk_image.save(image_bytes, 'png')
            image_bytes.seek(0)
            await channel.send(file=File(fp=image_bytes, filename='bonk.png'))

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
