from discord.ext.commands import AutoShardedBot


class ModifiedAutoShardedBot(AutoShardedBot):
    def __init__(self, command_prefix, *, intents, **options):
        super().__init__(command_prefix, intents=intents, **options)

