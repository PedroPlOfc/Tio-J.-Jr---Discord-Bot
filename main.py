import discord
import asyncio
import yt_dlp
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def bot_start():

    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Client(intents=intents)

    # Configurações do yt-dlp
    yt_dl_options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch", # Busca automaticamente no YouTube se não for link
        "extractor_args": {"youtube": {"player_client": "web"}}
    }

    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    # Configurações do FFmpeg
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    @bot.event 
    async def on_ready():
        print(f"🤖 {bot.user} está online e pronto para tocar!")

    @bot.event 
    async def on_message(message): 
        if message.author.bot:
            return

        # Comando para tocar música: !play <link ou nome>
        if message.content.startswith("!!play"):
            # Verifica se quem enviou o comando está em um canal de voz
            if not message.author.voice:
                await message.channel.send("Entra na misera do canal pra eu tocar o djabo da música, cachorro mago")
                return

            voice_channel = message.author.voice.channel
            busca = message.content[6:].strip() # Pega o texto após "!play "

            if not busca:
                await message.channel.send("Digita a disgraça da musica. Ex: `!play Linkin Park Numb`")
                return

            await message.channel.send(f"🔍 Buscando por: **{busca}**...")

            # Se já não estiver conectado, conecta no canal de voz do usuário
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client:
                voice_client = await voice_channel.connect()

            # Extrai as informações da música via yt-dlp em thread separada para não travar o bot
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busca, download=False))

            if 'entries' in data:
                data = data['entries'][0] # Pega o primeiro resultado da busca por texto

            url_audio = data['url']
            titulo = data.get('title', 'Música')

            # Para o áudio atual se já estiver tocando algo
            if voice_client.is_playing():
                voice_client.stop()

            # Toca a nova música
            player = discord.FFmpegPCMAudio(url_audio, **ffmpeg_options)
            voice_client.play(player)

            await message.channel.send(f"🎶 Tocando agora: **{titulo}**")

        # Comando para parar e desconectar: $stop ou $leave
        elif message.content.startswith("$stop") or message.content.startswith("$leave"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_client.disconnect()
                await message.channel.send("Desconectado do canal de voz.")

    bot.run(TOKEN)

if __name__ == "__main__":
    bot_start()