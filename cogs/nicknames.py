import sqlite3

from discord.ext import commands

from lib.embeds import *


class Nicknames(commands.Cog):
    db = 'data/nicknames.db'
    help = {
        KEY_TITLE: 'Nicknames',
        KEY_DESCRIPTION: 'Manages a database of manually-set custom nicknames for members of the server.',
        KEY_COMMAND: '!cb nicknames',
        KEY_SUBCOMMANDS: [
            {
                KEY_EMOJI: '🧾',
                KEY_TITLE: 'list',
                KEY_DESCRIPTION: 'Lists all of the existing custom nicknames.',
                KEY_EXAMPLE: '!cb nn list'
            },
            {
                KEY_EMOJI: '📝',
                KEY_TITLE: 'set [member] [nickname]',
                KEY_DESCRIPTION: 'Sets the nickname for the given member.',
                KEY_EXAMPLE: '!cb nn set "Lovegood#0001" "The Boba Queen"'
            },
            {
                KEY_EMOJI: '🧼',
                KEY_TITLE: 'delete [member]',
                KEY_DESCRIPTION: 'Deletes the nickname for the given member.',
                KEY_EXAMPLE: '!cb nn delete "Lovegood#0001"'
            }
        ]
    }

    def __init__(self, bot):
        self.bot = bot
        with sqlite3.connect(self.db) as connection:
            c = connection.cursor()
            c.execute(
                '''CREATE TABLE IF NOT EXISTS `nicknames` (
                    `id` INTEGER PRIMARY KEY UNIQUE,
                    `nickname` TEXT NOT NULL UNIQUE
                );''')
            connection.commit()
            c.close()

    @commands.command(aliases=['nickname', 'nn'])
    async def nicknames(self, ctx, command: str = None, *args):
        if command in ['add', 'change', 'insert', 'set', 'update'] and len(args) > 1:
            await self.insert_or_update_nickname(ctx, args)
        elif command in ['del', 'delete', 'remove', 'rm'] and len(args) >= 1:
            await self.delete_nickname(ctx, args)
        elif command in ['all', 'list', 'ls', 'show'] and len(args) == 0:
            await self.list_nicknames(ctx)
        else:
            await ctx.send(embed=create_help_embed(self.help))

    async def insert_or_update_nickname(self, ctx, args):
        user_str = args[0]
        member = Nicknames.get_member_from_guild(ctx, user_str)
        nickname = " ".join(args[1:])
        if member:
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM nicknames WHERE id=?', (member.id,))
                if c.fetchone():
                    c.execute('UPDATE nicknames SET nickname=? WHERE id=?', (nickname, member.id))
                    embed_msg = f'Updated nickname **{nickname}** for user **{member}**.'
                else:
                    c.execute('INSERT INTO nicknames VALUES (?, ?)', (member.id, nickname))
                    embed_msg = f'Added nickname **{nickname}** for user **{member}**.'
                c.close()
            await ctx.send(embed=create_basic_embed(embed_msg, EMOJI_SUCCESS))
        else:
            await Nicknames.on_member_not_found(ctx, user_str)

    async def delete_nickname(self, ctx, args):
        user_str = " ".join(args)
        member = Nicknames.get_member_from_guild(ctx, user_str)
        if member:
            with sqlite3.connect(self.db) as connection:
                c = connection.cursor()
                c.execute('SELECT * FROM nicknames WHERE id=?', (member.id,))
                row = c.fetchone()
                if row:
                    c.execute('DELETE FROM nicknames WHERE id=?', (member.id,))
                    embed_msg = f'Deleted nickname **{row[1]}** for user **{member}**.'
                    embed_emoji = EMOJI_SUCCESS
                else:
                    embed_msg = f'User **{member}** does not currently have a nickname.'
                    embed_emoji = EMOJI_WARNING
                c.close()
            await ctx.send(embed=create_basic_embed(embed_msg, embed_emoji))
        else:
            await Nicknames.on_member_not_found(ctx, user_str)

    async def list_nicknames(self, ctx):
        table_rows = []
        with sqlite3.connect(self.db) as connection:
            c = connection.cursor()
            for row in c.execute('SELECT * FROM nicknames'):
                member = ctx.guild.get_member(row[0])
                table_rows.append((row[1], str(member), member.display_name))
            c.close()
        title = f'Nicknames in "{ctx.guild.name}"'
        headers = ("🤝 Nickname", "💬 Discord Handle", "🔍 Display Name")
        embed = create_table_embed(title, headers, table_rows)
        await ctx.send(embed=embed)

    @staticmethod
    async def on_member_not_found(ctx, user_str):
        await ctx.send(embed=create_basic_embed(f'Could not find member named **{user_str}**.', EMOJI_ERROR))

    @staticmethod
    def get_member_from_guild(ctx, identifier):
        if isinstance(identifier, int):
            return ctx.guild.get_member(identifier)
        elif identifier.isnumeric():
            return ctx.guild.get_member(int(identifier))
        else:
            return ctx.guild.get_member_named(identifier)

    def get_member_from_db(self, ctx, sql, arg):
        with sqlite3.connect(self.db) as connection:
            c = connection.cursor()
            c.execute(sql, (arg,))
            results = c.fetchall()
            c.close()
        if results and len(results) == 1:
            return Nicknames.get_member_from_guild(ctx, results[0][0])

    def get_member_by_nickname(self, ctx, nickname):
        return self.get_member_from_db(ctx, 'SELECT * FROM nicknames WHERE nickname=?', nickname)

    # TODO: Is this necessary?
    def get_member_by_id(self, ctx, member_id):
        return self.get_member_from_db(ctx, 'SELECT * FROM nicknames WHERE id=?', member_id)


def setup(bot):
    bot.add_cog(Nicknames(bot))
