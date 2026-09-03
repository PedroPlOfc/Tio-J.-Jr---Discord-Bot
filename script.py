import discord

class MeuPrimeiroBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="$",
            intents=intents
        )
    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"O bot {self.user} foi ligado com sucesso.") 

bot = MeuPrimeiroBot()

bot.run()