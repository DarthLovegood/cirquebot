from PIL import Image
from asyncio import Lock, create_task, sleep
from datetime import datetime, timezone
from discord import File
from discord.ext import commands, tasks
from io import BytesIO
from lib.embeds import create_basic_embed, EMOJI_ERROR
from lib.utils import log
from random import choice
from re import compile, IGNORECASE

COG_INTRO_SESSION = 'AbsIntroSession'
COG_GAME_SESSION = 'AbsGameSession'

AB_ONE = 'ONE'  # Sometimes called as "2".
AB_INNER_THREE = 'INNER_THREE'
AB_OUTER_THREE = 'OUTER_THREE'
AB_THREE = 'THREE'  # Only valid if exactly one of AB_INNER_THREE or AB_OUTER_THREE is selected.
AB_FIVE = 'FIVE'  # Sometimes called as "4".
AB_SIX = 'SIX'
AB_SEVEN = 'SEVEN'  # Sometimes called as "8".
AB_INNER_NINE = 'INNER_NINE'
AB_OUTER_NINE = 'OUTER_NINE'
AB_NINE = 'NINE'  # Only valid if exactly one of AB_INNER_NINE or AB_OUTER_NINE is selected.
AB_ELEVEN = 'ELEVEN'  # Sometimes called as "10".
AB_TWELVE = 'TWELVE'

AB_POSITIONS = {
    AB_ONE: (389, 67),
    AB_INNER_THREE: (368, 233),
    AB_OUTER_THREE: (510, 233),
    AB_FIVE: (389, 399),
    AB_SIX: (260, 456),
    AB_SEVEN: (131, 399),
    AB_INNER_NINE: (152, 233),
    AB_OUTER_NINE: (10, 233),
    AB_ELEVEN: (131, 67),
    AB_TWELVE: (260, 10)
}

AB_REGEXES = {
    AB_ONE: compile(r'^(1|one|2|two)$', IGNORECASE),
    AB_INNER_THREE: compile(r'^((i[ner]* ?(3|three))|((3|three) ?i[ner]*))$', IGNORECASE),
    AB_OUTER_THREE: compile(r'^((o[uter]* ?(3|three))|((3|three) ?o[uter]*))$', IGNORECASE),
    AB_THREE: compile(r'^(3|three)$', IGNORECASE),
    AB_FIVE: compile(r'^(4|four|5|five)$', IGNORECASE),
    AB_SIX: compile(r'^(6|six)$', IGNORECASE),
    AB_SEVEN: compile(r'^(7|seven|8|eight)$', IGNORECASE),
    AB_INNER_NINE: compile(r'^((i[ner]* ?(9|nine))|((9|nine) ?i[ner]*))$', IGNORECASE),
    AB_OUTER_NINE: compile(r'^((o[uter]* ?(9|nine))|((9|nine) ?o[uter]*))$', IGNORECASE),
    AB_NINE: compile(r'^(9|nine)$', IGNORECASE),
    AB_ELEVEN: compile(r'^(10|ten|11|eleven)$', IGNORECASE),
    AB_TWELVE: compile(r'^(12|twelve)$', IGNORECASE)
}

ABS_NUMBER_OF_FLASHES = 4  # This must match the lengths of TEXT_GAME_CALL_IDENTIFIERS and TEXT_GAME_CALL_SUBTITLES.

ABS_DIAGRAM_DURATION_MS = 6000
ABS_INTERVAL_DURATION_MS = 3000
ABS_FLASH_DURATION_MS = 60
ABS_ENDING_DURATION_MS = 1500

MS_IN_SECONDS = 1000

INTRO_UPDATE_INTERVAL_SECONDS = 5
INTRO_NUMBER_OF_UPDATES = 6
INTRO_DURATION_SECONDS = INTRO_UPDATE_INTERVAL_SECONDS * INTRO_NUMBER_OF_UPDATES

FILENAME_ABS_BACKGROUND = 'assets/abs_background.png'
FILENAME_ABS_DIAGRAM = 'assets/abs_diagram.png'
FILENAME_ABS_FLASH = 'assets/abs_flash.png'
FILENAME_ABS_NEUTRAL = 'assets/abs_neutral.png'
FILENAME_ABS_GIF = 'abs.gif'

URL_ARTIST_CREDIT = 'https://www.redbubble.com/people/Night-Valien/shop'
URL_REVAN_ICON = 'https://cdn.discordapp.com/attachments/770579028624801802/914390225743151134/revan_icon.png'
URL_REVAN_THUMBNAIL = 'https://cdn.discordapp.com/attachments/770579028624801802/914325770732707890/revan.png'
URL_HK_ICON = 'https://cdn.discordapp.com/attachments/770579028624801802/915512461359214602/hk_icon.png'

TEXT_INTRO_AUTHOR = 'Revan says...'
TEXT_INTRO_TITLE = 'So, you want to be an ab caller?'
TEXT_INTRO_SUBTITLE = '*My Revanites understand what you do not.*'
TEXT_INTRO_PLAYERS_HEADER = '\n\n👥 \u200B __**PLAYERS**__'
TEXT_INTRO_PROMPT = f'\n\n**Send any message in this channel if you\'d like to join.**'
TEXT_INTRO_TIME_FORMAT = 'The game will begin in approximately {0} seconds.'
TEXT_INTRO_FOOTER = 'Prepare yourselves - the game is about to begin.'

TEXT_GAME_START_TITLE = 'The game has begun.'
TEXT_GAME_START_SUBTITLE = '*Your interference will be your undoing!*'
TEXT_GAME_START_DIRECTIONS = '\n\n**Aberrations will become active. Watch closely!** \u200B 👀' \
                             '\n \u200B \u200B \u200B 📵 Don\'t click out of your Discord window.' \
                             '\n \u200B \u200B \u200B 🚷 Don\'t type anything before you\'re told to.'

TEXT_GAME_EMOJI_AB_ACTIVE = '🟣'
TEXT_GAME_EMOJI_AB_BLANK = '⚫'
TEXT_GAME_CALL_TITLE_FORMAT = 'Call the {0} aberration now. \u200B '
TEXT_GAME_CALL_IDENTIFIERS = ['FIRST', 'SECOND', 'THIRD', 'FOURTH']
TEXT_GAME_CALL_SUBTITLES = ['*For the galaxy to survive, you must fall!*', '*No! I won\'t be denied!*',
                            '*I will never give in!*', '*You cannot stop the sacrifice!*']
TEXT_GAME_PLAYERS_LABEL = '\n\n👥 **PLAYERS:** \u200B '
TEXT_GAME_PLAYERS_NONE = 'None.'

TEXT_GAME_DEATH_TITLE_SINGULAR = 'Someone has died.'
TEXT_GAME_DEATH_TITLE_PLURAL_FORMAT = '{0} people have died.'
TEXT_GAME_DEATH_SUBTITLE = '*You could have avoided this fate!*'
TEXT_GAME_DEATH_LABEL = '\n\n☠️ **DEAD:** \u200B '
TEXT_GAME_DISQUALIFIED_TITLE = 'Observation: Someone has started typing too early!'
TEXT_GAME_DISQUALIFIED_SUBTITLE = '*Assessment: This meatbag will not provide optimal killing satisfaction.*' \
                                  '\n*Assurance: I will end their pathetic life, master.*'

TEXT_GAME_WON_TITLE_SINGULAR = 'We have a winner!'
TEXT_GAME_WON_TITLE_PLURAL_FORMAT = 'We have {0} winners!'
TEXT_GAME_WON_SUBTITLE = '*I can\'t believe you...*'
TEXT_GAME_WON_LABEL = '\n\n🎉 **WINNERS:** \u200B '
TEXT_GAME_LOST_TITLE = 'GAME OVER!'
TEXT_GAME_LOST_SUBTITLE = '*You are all fools!*'
TEXT_GAME_LOST_LABEL = '\n\n🪦 **LOSERS:** \u200B '


class AbsGame(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_channel = None
        self.active_channel_lock = Lock()

    @commands.command()
    async def abs(self, ctx):
        # Only recognize this command in the #revan-abs-game channel for now.
        if ctx.channel.id != 914637952825573377:
            return

        bot_member = ctx.guild.get_member(self.bot.user.id)
        if not ctx.channel.permissions_for(bot_member).send_messages:
            log(f'ERROR: Missing permission to send messages in channel "{ctx.channel.name}".')
            return

        async with self.active_channel_lock:
            if self.active_channel:
                log(f'Already running an Abs Game in "{self.active_channel.name}". '
                    f'Ignoring command from {ctx.author.name}#{ctx.author.discriminator}.')
                if ctx.channel.id != self.active_channel.id:
                    embed_text = f'Sorry {ctx.author.mention}, I\'m too busy right now! Please wait a little bit.'
                    await ctx.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))
            else:
                self.active_channel = ctx.channel
                intro_session_cog = AbsGame.AbsIntroSession(ctx.channel, ctx.author, self.start_game)
                self.bot.add_cog(intro_session_cog)
                await intro_session_cog.start()

    async def start_game(self, players):
        async with self.active_channel_lock:
            if self.active_channel:
                self.bot.remove_cog(COG_INTRO_SESSION)
                game_session_cog = AbsGame.AbsGameSession(self.active_channel, players, self.finish_game)
                self.bot.add_cog(game_session_cog)
                await game_session_cog.start()
            else:
                log(f'ERROR: Attempted to start game with no active channel. This should never happen.')
                embed_text = 'Something went wrong while trying to start the game. Sorry!'
                await ctx.channel.send(embed=create_basic_embed(embed_text, EMOJI_ERROR))

    async def finish_game(self):
        async with self.active_channel_lock:
            self.active_channel = None
            self.bot.remove_cog(COG_GAME_SESSION)

    class AbsIntroSession(commands.Cog):
        def __init__(self, channel, player, callback):
            self.channel = channel
            self.on_finish = callback  # Will be called with the final list of players as an argument.
            self.lock = Lock()  # This lock protects all the fields below it.
            self.players = [player]
            self.time_remaining = INTRO_DURATION_SECONDS + INTRO_UPDATE_INTERVAL_SECONDS
            self.message = None

        async def start(self):
            embed = create_basic_embed()
            embed.title = TEXT_INTRO_TITLE
            embed.set_author(name=TEXT_INTRO_AUTHOR, icon_url=URL_REVAN_ICON, url=URL_ARTIST_CREDIT)
            embed.set_thumbnail(url=URL_REVAN_THUMBNAIL)
            embed.set_footer(text=TEXT_INTRO_TIME_FORMAT.format(INTRO_DURATION_SECONDS))

            async with self.lock:
                embed.description = self.get_description_string()
                self.message = await self.channel.send(embed=embed)
                log(f'Initializing a new Abs Game in "{self.channel.name}". '
                    f'Accepting players for {self.time_remaining} seconds!')
                log(f'STARTING PLAYER: {self.players[0].name}#{self.players[0].discriminator}', indent=1)

            self.countdown.start()

        @tasks.loop(seconds=INTRO_UPDATE_INTERVAL_SECONDS, count=INTRO_NUMBER_OF_UPDATES + 1)
        async def countdown(self):
            async with self.lock:
                self.time_remaining -= INTRO_UPDATE_INTERVAL_SECONDS
                log(f'UPDATE: {self.time_remaining} seconds remaining.', indent=1)
                await self.refresh_message()

        @commands.Cog.listener()
        async def on_message(self, message):
            async with self.lock:
                user = message.author
                if (message.channel.id == self.channel.id) and (not user.bot) and (user not in self.players):
                    log(f'NEW PLAYER: {user.name}#{user.discriminator}', indent=1)
                    self.players.append(user)
                    await self.refresh_message()

        # This method assumes that self.lock is already held by the caller.
        async def refresh_message(self):
            if not self.message:
                return
            embed = self.message.embeds[0]
            embed.description = self.get_description_string()
            if self.time_remaining > 0:
                embed.set_footer(text=TEXT_INTRO_TIME_FORMAT.format(self.time_remaining))
            else:
                embed.description += '\n \u200B'
                embed.set_footer(text=TEXT_INTRO_FOOTER)
            await self.message.edit(embed=embed)

        # This method assumes that self.lock is already held by the caller.
        def get_description_string(self):
            description_string = TEXT_INTRO_SUBTITLE + TEXT_INTRO_PLAYERS_HEADER
            for i, player in list(enumerate(self.players, start=1)):
                description_string += f'\n**`{i})`** \u200B {player.mention}'
            if self.time_remaining > 0:
                description_string += TEXT_INTRO_PROMPT
            return description_string

        @countdown.after_loop
        async def finish(self):
            async with self.lock:
                log(f'No longer accepting players in "{self.channel.name}".')
                await self.on_finish(self.players)

    class AbsGameSession(commands.Cog):
        def __init__(self, channel, players, callback):
            self.channel = channel
            self.selected_abs = AbsGame.AbsGameSession.select_random_abs()
            self.wait_task = None
            self.on_finish = callback  # Will be called with no arguments.
            self.lock = Lock()  # This lock protects all the fields below it.
            self.players_alive = players.copy()
            self.players_dead = []
            self.current_ab = ''
            self.ab_guesses = {}

        async def start(self):
            log(f'Starting the Abs Game in "{self.channel.name}"!')
            log(f'SELECTED ABS: {self.selected_abs}', indent=1)
            log(f'PLAYERS: {AbsGame.AbsGameSession.get_players_string(self.players_alive)}', indent=1)

            abs_gif_file, gif_duration_seconds = AbsGame.AbsGameSession.create_abs_gif(self.selected_abs)

            embed = AbsGame.AbsGameSession.create_game_embed(
                title=TEXT_GAME_START_TITLE,
                subtitle=TEXT_GAME_START_SUBTITLE,
                description=TEXT_GAME_START_DIRECTIONS,
                show_no_players_text=False)
            embed.set_image(url=f'attachment://{FILENAME_ABS_GIF}')
            message = await self.channel.send(embed=embed, file=abs_gif_file)

            log(f'LINK TO GIF: {message.embeds[0].image.url}', indent=1)
            log(f'Going to sleep for {gif_duration_seconds} seconds while the players watch the GIF.')
            self.wait_task = create_task(self.wait_for_gif(gif_duration_seconds))

        async def wait_for_gif(self, gif_duration_seconds):
            await sleep(gif_duration_seconds)
            self.call_abs.start()

        # Requires intents.typing in order to work.
        @commands.Cog.listener()
        async def on_typing(self, channel, user, unused_datetime):
            async with self.lock:
                if (channel.id == self.channel.id) and (not self.current_ab) and (user in self.players_alive):
                    log(f'{user.name}#{user.discriminator} is disqualified for typing too early.')
                    await self.disqualify_player(user)

        @commands.Cog.listener()
        async def on_message(self, message):
            async with self.lock:
                user = message.author
                if (message.channel.id == self.channel.id) and (not user.bot):
                    if user in self.players_alive:
                        if self.current_ab:
                            log(f'ALERT: Got a guess from {user.name}#{user.discriminator}.', indent=1)
                            self.ab_guesses[user] = message.content
                        else:
                            log(f'{user.name}#{user.discriminator} is disqualified for sending a message too early.')
                            await self.disqualify_player(user)
                    else:
                        log(f'Got an extraneous message from {user.name}#{user.discriminator}: "{message.content}"')

        # This method assumes that self.lock is already held by the caller.
        async def disqualify_player(self, user):
            self.players_alive.remove(user)
            self.players_dead.append(user)

            embed = AbsGame.AbsGameSession.create_game_embed(
                title=TEXT_GAME_DISQUALIFIED_TITLE,
                subtitle=TEXT_GAME_DISQUALIFIED_SUBTITLE,
                icon_url=URL_HK_ICON,
                players_label=TEXT_GAME_DEATH_LABEL,
                players=[user])
            await self.channel.send(embed=embed)

            if not self.players_alive:
                self.wait_task.cancel()
                await self.finish()

        @tasks.loop(seconds=ABS_INTERVAL_DURATION_MS // MS_IN_SECONDS, count=ABS_NUMBER_OF_FLASHES + 1)
        async def call_abs(self):
            async with self.lock:
                if self.current_ab:
                    await self.evaluate_ab_guesses()

                index = self.call_abs.current_loop
                if (index == len(self.selected_abs)) or (not self.players_alive):
                    self.call_abs.cancel()
                    return

                self.current_ab = self.selected_abs[index]
                self.ab_guesses.clear()

                embed = AbsGame.AbsGameSession.create_game_embed(
                    title=TEXT_GAME_CALL_TITLE_FORMAT.format(TEXT_GAME_CALL_IDENTIFIERS[index]),
                    current_progress=index + 1,
                    subtitle=TEXT_GAME_CALL_SUBTITLES[index],
                    players_label=TEXT_GAME_PLAYERS_LABEL,
                    players=self.players_alive)
                await self.channel.send(embed=embed)
                log(f'Now collecting player guesses for aberration #{index + 1}: "{self.current_ab}"')

        # This method assumes that self.lock is already held by the caller.
        async def evaluate_ab_guesses(self):
            killed_players = []
            log(f'Evaluating player guesses for aberration: "{self.current_ab}"')

            for user, guess_string in self.ab_guesses.items():
                if AbsGame.AbsGameSession.is_guess_correct(guess_string, self.current_ab, self.selected_abs):
                    log(f'CORRECT: {user.name}#{user.discriminator} guessed "{guess_string}".', indent=1)
                else:
                    log(f'INCORRECT: {user.name}#{user.discriminator} guessed "{guess_string}".', indent=1)
                    killed_players.append(user)

            for user in self.players_alive:
                if user not in self.ab_guesses:
                    log(f'TOO SLOW: {user.name}#{user.discriminator} did not make a guess in time!', indent=1)
                    killed_players.append(user)

            killed_players = [user for user in killed_players if user not in self.players_dead]
            self.players_alive = [user for user in self.players_alive if user not in killed_players]

            if killed_players:
                self.players_dead.extend(killed_players)
                log(f'The following players have died: {AbsGame.AbsGameSession.get_players_string(killed_players)}')
                embed = AbsGame.AbsGameSession.create_game_embed(
                    title_singular=TEXT_GAME_DEATH_TITLE_SINGULAR,
                    title_plural_format=TEXT_GAME_DEATH_TITLE_PLURAL_FORMAT,
                    subtitle=TEXT_GAME_DEATH_SUBTITLE,
                    players_label=TEXT_GAME_DEATH_LABEL,
                    players=killed_players)
                await self.channel.send(embed=embed)

        @call_abs.after_loop
        async def on_loop_finish(self):
            async with self.lock:
                await self.finish()

        # This method assumes that self.lock is already held by the caller.
        async def finish(self):
            log(f'The Abs Game in "{self.channel.name}" has ended!')
            log(f'WINNERS: {AbsGame.AbsGameSession.get_players_string(self.players_alive)}', indent=1)
            log(f'LOSERS: {AbsGame.AbsGameSession.get_players_string(self.players_dead)}', indent=1)
            if self.players_alive:
                embed = AbsGame.AbsGameSession.create_game_embed(
                    title_singular=TEXT_GAME_WON_TITLE_SINGULAR,
                    title_plural_format=TEXT_GAME_WON_TITLE_PLURAL_FORMAT,
                    subtitle=TEXT_GAME_WON_SUBTITLE,
                    show_thumbnail=True,
                    players_label=TEXT_GAME_WON_LABEL,
                    players=self.players_alive)
            else:
                embed = AbsGame.AbsGameSession.create_game_embed(
                    title=TEXT_GAME_LOST_TITLE,
                    subtitle=TEXT_GAME_LOST_SUBTITLE,
                    show_thumbnail=True,
                    players_label=TEXT_GAME_LOST_LABEL,
                    players=self.players_dead)
            await self.channel.send(embed=embed)
            await self.on_finish()

        @staticmethod
        def is_guess_correct(guess_string: str, current_ab: str, selected_abs: str):
            if AB_REGEXES[current_ab].match(guess_string):
                return True
            elif (((current_ab == AB_INNER_THREE) and (AB_OUTER_THREE not in selected_abs))
                  or ((current_ab == AB_OUTER_THREE) and (AB_INNER_THREE not in selected_abs))):
                return AB_REGEXES[AB_THREE].match(guess_string)
            elif (((current_ab == AB_INNER_NINE) and (AB_OUTER_NINE not in selected_abs))
                  or ((current_ab == AB_OUTER_NINE) and (AB_INNER_NINE not in selected_abs))):
                return AB_REGEXES[AB_NINE].match(guess_string)
            else:
                return False

        @staticmethod
        def create_game_embed(title: str = '', title_singular: str = '', title_plural_format: str = '',
                              current_progress: int = 0, total_progress: int = ABS_NUMBER_OF_FLASHES,
                              subtitle: str = '', description: str = '',
                              icon_url: str = URL_REVAN_ICON, show_thumbnail: bool = False,
                              players_label: str = '', players: list = [], show_no_players_text: bool = True):
            if title_singular and len(players) == 1:
                embed_title = title_singular
            elif title_plural_format:
                embed_title = title_plural_format.format(len(players))
            else:
                embed_title = title

            if current_progress:
                embed_title += TEXT_GAME_EMOJI_AB_ACTIVE * current_progress
                embed_title += TEXT_GAME_EMOJI_AB_BLANK * (total_progress - current_progress)

            embed = create_basic_embed(subtitle + description + players_label)
            embed.set_author(name=embed_title, icon_url=icon_url)

            if show_thumbnail:
                embed.set_thumbnail(url=URL_REVAN_THUMBNAIL)

            if players or show_no_players_text:
                embed.description += AbsGame.AbsGameSession.get_players_string(players, mention_players=True)

            return embed

        @staticmethod
        def get_players_string(players: list = [], mention_players: bool = False):
            if players:
                if mention_players:
                    player_string_list = [user.mention for user in players]
                else:
                    player_string_list = [f'{user.name}#{user.discriminator}' for user in players]
                return ', '.join(player_string_list)
            else:
                return TEXT_GAME_PLAYERS_NONE

        @staticmethod
        def select_random_abs(number_of_abs: int = ABS_NUMBER_OF_FLASHES):
            selected_abs = []
            possible_abs = list(AB_POSITIONS.keys())
            while len(selected_abs) < number_of_abs:
                random_ab = choice(possible_abs)
                if random_ab not in selected_abs:
                    selected_abs.append(random_ab)
            return selected_abs

        @staticmethod
        def get_flash_image(base_image: Image, ab: str = None):
            if ab in AB_POSITIONS:
                flash_image = Image.open(FILENAME_ABS_FLASH)
                base_image.paste(flash_image, AB_POSITIONS[ab], flash_image)
            return base_image

        @staticmethod
        def get_interval_image(selected_abs: list):
            background_image = Image.open(FILENAME_ABS_BACKGROUND)
            neutral_ab_image = Image.open(FILENAME_ABS_NEUTRAL)
            for ab in selected_abs:
                background_image.paste(neutral_ab_image, AB_POSITIONS[ab], neutral_ab_image)
            return background_image

        @staticmethod
        def create_abs_gif(selected_abs: list,
                           diagram_duration_ms: int = ABS_DIAGRAM_DURATION_MS,
                           flash_duration_ms: int = ABS_FLASH_DURATION_MS,
                           interval_duration_ms: int = ABS_INTERVAL_DURATION_MS):
            interval_image = AbsGame.AbsGameSession.get_interval_image(selected_abs)
            flash_images = [AbsGame.AbsGameSession.get_flash_image(interval_image.copy(), ab) for ab in selected_abs]
            diagram_image = Image.open(FILENAME_ABS_DIAGRAM)

            frame_images = [interval_image]  # First frame image is not included because it's used to call save() below.
            durations_ms = [diagram_duration_ms, interval_duration_ms]
            for flash_image in flash_images:
                frame_images.extend([flash_image, interval_image])
                durations_ms.extend([flash_duration_ms, interval_duration_ms])
            durations_ms[-1] = ABS_ENDING_DURATION_MS  # Shorten the duration of the very last frame.
            total_duration_seconds = sum(durations_ms) // MS_IN_SECONDS

            with BytesIO() as image_bytes:
                diagram_image.save(image_bytes, 'gif', save_all=True, append_images=frame_images, duration=durations_ms)
                image_bytes.seek(0)
                return File(fp=image_bytes, filename=FILENAME_ABS_GIF), total_duration_seconds


def setup(bot):
    bot.add_cog(AbsGame(bot))
