import asyncio
import numbers
from datetime import datetime
from json import loads

import aiohttp
from discord import NotFound, Forbidden

from lib.embeds import EMOJI_ERROR, create_basic_embed

TEXT_INVALID_MESSAGE_LINK = 'Please make sure the message link is valid.'


def log(text, indent=0):
    timestamp = str(datetime.now())[:-3]
    print(f'{timestamp}  |  {"    " * indent}{text}')


def extract_channel_id(message_link):
    return int(message_link.split('/')[-2])


def extract_message_id(message_link):
    return int(message_link.split('/')[-1])


def get_message_link_string(message_link):
    return f'[{extract_message_id(message_link)}]({message_link})'


def get_channel(ctx, channel_str):
    return ctx.guild.get_channel(int(channel_str[2:-1]))


async def fetch_message(ctx, message_link):
    try:
        channel_id = extract_channel_id(message_link)
        channel = ctx.guild.get_channel(channel_id)

        if channel:
            return await channel.fetch_message(extract_message_id(message_link))
        else:
            raise NotFound(f'Channel {channel_id} not found.')
    except (IndexError, ValueError, Forbidden, NotFound):
        return None


async def fetch_dict_from_message(ctx, message_link, required_keys=[], enforce_numeric_values=False):
    message = await fetch_message(ctx, message_link)

    if not message:
        await ctx.send(embed=create_basic_embed(TEXT_INVALID_MESSAGE_LINK, EMOJI_ERROR))
        return

    try:
        content = message.content
        message_dict = loads(content[content.index("{"):content.rindex("}") + 1])
    except ValueError:
        await ctx.send(embed=create_basic_embed('Please make sure the message is properly formatted.', EMOJI_ERROR))
        return None

    clean_dict = {}

    for key in required_keys:
        if key in message_dict:
            value = message_dict[key]
            if enforce_numeric_values and not isinstance(value, numbers.Number):
                await ctx.send(embed=create_basic_embed('Please make sure all values are numeric.', EMOJI_ERROR))
                return None
            clean_dict[key] = value
        else:
            await ctx.send(embed=create_basic_embed(f'Message is missing required key **{key}**.', EMOJI_ERROR))
            return None

    return clean_dict


async def get_attachment_data(message):
    data = None
    if len(message.attachments) == 1:
        data = await message.attachments[0].read()
    return data


async def get_embed_data(message):
    data = None
    await wait_for_embed(message, 3)  # Allow up to 3 seconds for the embed to load.
    if len(message.embeds) == 1:
        async with aiohttp.ClientSession() as session:
            async with session.get(message.embeds[0].url) as response:
                if response.status == 200:
                    data = await response.read()
    return data


async def wait_for_embed(message, seconds):
    for i in range(seconds):
        if message.embeds:
            return
        else:
            await asyncio.sleep(1)
