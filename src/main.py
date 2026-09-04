import discord
import asyncio
import yt_dlp
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Configuração opcional do Spotify (caso tenha cadastrado no .env)
sp = None
if SPOTIFY_ID and SPOTIFY_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_ID,
        client_secret=SPOTIFY_SECRET
    ))

def extrair_busca_spotify(url):
    """Converte links do Spotify em termos de busca de texto"""
    if not sp:
        return url
    try:
        if "track" in url:
            track_info = sp.track(url)
            return f"{track_info['name']} {track_info['artists'][0]['name']}"
        elif "playlist" in url:
            playlist_info = sp.playlist_tracks(url)
            primeira_faixa = playlist_info['items'][0]['track']
            return f"{primeira_faixa['name']} {primeira_faixa['artists'][0]['name']}"
    except Exception as e:
        print(f"Erro ao processar Spotify: {e}")
    return url

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
        "default_search": "ytsearch",
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
        if message.content.startswith("!play"):
            if not message.author.voice:
                await message.channel.send("Entra na misera do canal pra eu tocar o djabo da música, cachorro mago")
                return

            voice_channel = message.author.voice.channel
            
            # Divide o comando do argumento com segurança
            partes = message.content.split(" ", 1)
            if len(partes) < 2 or not partes[1].strip():
                await message.channel.send("Digita a disgraça da musica. Ex: `!play Linkin Park Numb`")
                return

            entrada = partes[1].strip()

            # Processa link do Spotify se presente
            if "spotify.com" in entrada:
                await message.channel.send("🟢 Link do Spotify detectado! Convertendo faixa...")
                busca = extrair_busca_spotify(entrada)
            else:
                busca = entrada

            await message.channel.send(f"🔍 Buscando por: **{busca}**...")

            # Conecta ao canal se ainda não estiver nele
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client:
                voice_client = await voice_channel.connect()

            # Extração dos dados do áudio via yt-dlp
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busca, download=False))
            except Exception as e:
                await message.channel.send("Não consegui encontrar ou carregar essa música. Tente outro termo!")
                print(f"Erro no yt-dlp: {e}")
                return

            if 'entries' in data:
                data = data['entries'][0]

            url_audio = data['url']
            titulo = data.get('title', 'Música')

            if voice_client.is_playing():
                voice_client.stop()

            # Se o ffmpeg.exe estiver na raiz do projeto, utiliza o argumento executable="ffmpeg.exe"
            try:
                player = discord.FFmpegPCMAudio(url_audio, executable="ffmpeg.exe", **ffmpeg_options)
            except Exception:
                # Caso o FFmpeg já esteja instalado globalmente no PATH
                player = discord.FFmpegPCMAudio(url_audio, **ffmpeg_options)

            voice_client.play(player)

            await message.channel.send(f"🎶 Tocando agora: **{titulo}**")

        # Comando para parar e desconectar: !stop ou !leave
        elif message.content.startswith("!stop") or message.content.startswith("!leave"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_client.disconnect()
                await message.channel.send("Desconectado do canal de voz.")

    bot.run(TOKEN)

if __name__ == "__main__":
    bot_start()