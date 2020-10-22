from discord.ext import commands


class FilteredUser(commands.UserConverter):

    def __init__(self, *, allow_author:bool=False, allow_bots:bool=False):
        self.allow_author = allow_author
        self.allow_bots = allow_bots

    async def convert(self, ctx, argument):
        m = await super().convert(ctx, argument)
        if self.allow_author is False and ctx.author.id == m.id:
            raise commands.BadArgument("You can't run this command on yourself.")
        if self.allow_bots is False and m.bot:
            raise commands.BadArgument("You can't run this command on bots.")
        return m


class FilteredMember(FilteredUser):

    def __init__(self, *, allow_author:bool=False, allow_bots:bool=False):
        self.allow_author = allow_author
        self.allow_bots = allow_bots

    async def convert(self, ctx, argument):
        m = await super(commands.MemberConverter).convert(ctx, argument)
        if self.allow_author is False and ctx.author.id == m.id:
            raise commands.BadArgument("You can't run this command on yourself.")
        if self.allow_bots is False and m.bot:
            raise commands.BadArgument("You can't run this command on bots.")
        return m