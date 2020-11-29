import asyncio
import numbers
from json import loads

import aiohttp
from discord import NotFound

from embeds import EMOJI_ERROR, create_basic_embed


async def fetch_dict_from_message(ctx, message_link, required_keys=[], enforce_numeric_values=False):
    try:
        message = await ctx.fetch_message(int(message_link.split("/")[-1]))
    except (ValueError, NotFound):
        await ctx.send(embed=create_basic_embed('Please make sure the message link is valid.', EMOJI_ERROR))
        return None

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
