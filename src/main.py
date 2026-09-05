import os
import asyncio
from pathlib import Path
import discord
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import static_ffmpeg
static_ffmpeg.add_paths()

# Define o caminho do .env na pasta raiz (1 nível acima de src/)
env_path = Path(__file__).resolve().parent.parent /'.env'
load_dotenv(dotenv_path=env_path)

# TOKENS
TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Configuração do Spotify
sp = None
if SPOTIFY_ID and SPOTIFY_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_ID,
        client_secret=SPOTIFY_SECRET
    ))

# Dicionário global para armazenar a fila de músicas por servidor (guild)
queues = {}

def extrair_buscas_spotify(url):
    """Converte links do Spotify (faixas, playlists ou álbuns) em lista de buscas"""
    if not sp:
        return [url]
    
    buscas = []
    try:
        if "track" in url:
            track_info = sp.track(url)
            buscas.append(f"{track_info['name']} {track_info['artists'][0]['name']}")
        
        elif "playlist" in url:
            results = sp.playlist_items(url)
            for item in results['items']:
                track = item.get('track')
                if track and track.get('name'):
                    nome = track['name']
                    artista = track['artists'][0]['name']
                    buscas.append(f"{nome} {artista}")
                    
        elif "album" in url:
            results = sp.album_tracks(url)
            for track in results['items']:
                nome = track['name']
                artista = track['artists'][0]['name']
                buscas.append(f"{nome} {artista}")

    except Exception as e:
        print(f"Erro ao processar Spotify: {e}")
        return [url]

    return buscas if buscas else [url]


def extrair_buscas_youtube_mix(url, ytdl_flat):
    """Extrai os links ou títulos de todos os vídeos presentes em um Mix/Playlist do YouTube"""
    try:
        # Usa extract_flat para pegar a lista inteira rapidamente sem baixar/resolver os áudios
        data = ytdl_flat.extract_info(url, download=False)
        
        buscas = []
        if 'entries' in data:
            for entry in data['entries']:
                if entry:
                    # Pega a URL do vídeo individual da lista ou o título
                    video_url = entry.get('url') or entry.get('webpage_url') or entry.get('title')
                    if video_url:
                        buscas.append(video_url)
        return buscas if buscas else [url]
    except Exception as e:
        print(f"Erro ao extrair Mix do YouTube: {e}")
        return [url]


def bot_start():

    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Client(intents=intents)

    # Configuração padrão para tocar 1 vídeo individual
    yt_dl_options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "extractor_args": {"youtube": {"player_client": "web"}}
    }

    # Configuração especial para varrer Playlists/Mixes rapidamente (modo Flat)
    yt_dl_flat_options = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True
    }

    ytdl = yt_dlp.YoutubeDL(yt_dl_options)
    ytdl_flat = yt_dlp.YoutubeDL(yt_dl_flat_options)

    # Configurações do FFmpeg
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    # Tocar proxima música da fila
    def tocar_proxima(guild_id, voice_client, channel, loop):
        """Função recursiva chamada quando uma música termina para tocar a próxima da fila"""
        if guild_id in queues and len(queues[guild_id]) > 0:
            proxima = queues[guild_id].pop(0)
            
            async def carregar_e_tocar():
                await channel.send(f"🔍 Carregando próxima da fila...")
                try:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(proxima, download=False))
                    if 'entries' in data:
                        data = data['entries'][0]

                    url_audio = data['url']
                    titulo = data.get('title', 'Música')

                    try:
                        player = discord.FFmpegPCMAudio(url_audio, executable="ffmpeg.exe", **ffmpeg_options)
                    except Exception:
                        player = discord.FFmpegPCMAudio(url_audio, **ffmpeg_options)

                    voice_client.play(player, after=lambda e: tocar_proxima(guild_id, voice_client, channel, loop))
                    await channel.send(f"🎶 Tocando agora: **{titulo}**")
                except Exception as err:
                    await channel.send(f"Erro ao carregar faixa da fila. Tentando a próxima...")
                    print(f"Erro no loop tocar_proxima: {err}")
                    tocar_proxima(guild_id, voice_client, channel, loop)

            asyncio.run_coroutine_threadsafe(carregar_e_tocar(), loop)
        else:
            asyncio.run_coroutine_threadsafe(channel.send("✅ A fila de músicas terminou!"), loop)

    @bot.event 
    async def on_ready():
        print(f"🤖 {bot.user} está online e pronto para carregar Mixes completos!")

    @bot.event 
    async def on_message(message): 
        if message.author.bot:
            return

        guild_id = message.guild.id

        if guild_id not in queues:
            queues[guild_id] = []

        # Comando para tocar música ou playlist/mix: !play <link/nome>
        if message.content.startswith("!play"):
            if not message.author.voice:
                await message.channel.send("Entra na misera do canal pra eu tocar o djabo da música, cachorro mago")
                return

            voice_channel = message.author.voice.channel
            partes = message.content.split(" ", 1)
            
            if len(partes) < 2 or not partes[1].strip():
                await message.channel.send("Digita a disgraça da musica. Ex: `!play Linkin Park Numb`")
                return

            entrada = partes[1].strip()
            loop = asyncio.get_event_loop()

            # 1. PROCESSA MIX OU PLAYLIST DO YOUTUBE
            if ("youtube.com" in entrada or "youtu.be" in entrada) and ("list=" in entrada):
                await message.channel.send("🌀 **Mix/Playlist do YouTube detectado!** Mapeando músicas...")
                buscas = await loop.run_in_executor(None, lambda: extrair_buscas_youtube_mix(entrada, ytdl_flat))

            # 2. PROCESSA SPOTIFY
            elif "spotify.com" in entrada:
                await message.channel.send("🟢 **Link do Spotify detectado!** Processando faixas...")
                buscas = await loop.run_in_executor(None, lambda: extrair_buscas_spotify(entrada))

            # 3. BUSCA DE TEXTO OU VÍDEO ÚNICO
            else:
                buscas = [entrada]

            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client:
                voice_client = await voice_channel.connect()

            # SE JÁ ESTIVER TOCANDO: Adiciona todas as faixas diretamente na fila
            if voice_client.is_playing() or voice_client.is_paused():
                queues[guild_id].extend(buscas)
                if len(buscas) > 1:
                    await message.channel.send(f"📑 Mix/Playlist adicionado à fila! (**{len(buscas)} músicas** adicionadas)")
                else:
                    await message.channel.send(f"📝 Adicionado à fila: **{buscas[0]}**")
            
            # SE NÃO ESTIVER TOCANDO: Toca a primeira faixa e joga o resto na fila
            else:
                primeira = buscas[0]
                if len(buscas) > 1:
                    queues[guild_id].extend(buscas[1:])
                    await message.channel.send(f"📑 Mix detectado! Tocando a 1ª faixa e adicionando **{len(buscas)-1} músicas** à fila.")

                await message.channel.send(f"🔍 Buscando por: **{primeira}**...")
                
                try:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(primeira, download=False))
                    if 'entries' in data:
                        data = data['entries'][0]

                    url_audio = data['url']
                    titulo = data.get('title', 'Música')

                    try:
                        player = discord.FFmpegPCMAudio(url_audio, executable="ffmpeg.exe", **ffmpeg_options)
                    except Exception:
                        player = discord.FFmpegPCMAudio(url_audio, **ffmpeg_options)

                    voice_client.play(player, after=lambda e: tocar_proxima(guild_id, voice_client, message.channel, loop))
                    await message.channel.send(f"🎶 Tocando agora: **{titulo}**")
                except Exception as e:
                    await message.channel.send("Erro ao carregar a primeira música. Tentando a próxima da fila...")
                    print(f"Erro no yt-dlp: {e}")
                    tocar_proxima(guild_id, voice_client, message.channel, loop)

        # Comando para pular a música atual: !skip
        elif message.content.startswith("!skip"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                voice_client.stop()
                await message.channel.send("⏭️ Música pulada!")
            else:
                await message.channel.send("Não tem nenhuma música tocando no momento.")

        # Comando para ver a fila atual: !queue ou !fila
        elif message.content.startswith("!queue") or message.content.startswith("!fila"):
            if guild_id in queues and len(queues[guild_id]) > 0:
                lista_msg = "\n".join([f"{i+1}. {m}" for i, m in enumerate(queues[guild_id][:10])])
                sobrou = len(queues[guild_id]) - 10
                msg_extra = f"\n... e mais {sobrou} músicas na fila." if sobrou > 0 else ""
                await message.channel.send(f"📋 **Fila Atual ({len(queues[guild_id])} músicas):**\n```\n{lista_msg}{msg_extra}\n```")
            else:
                await message.channel.send("A fila está vazia no momento!")

        # Comando para parar, limpar a fila e desconectar: !stop ou !leave
        elif message.content.startswith("!stop") or message.content.startswith("!leave"):
            queues[guild_id] = []
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_client.disconnect()
                await message.channel.send("Fila limpa e bot desconectado do canal de voz.")

    bot.run(TOKEN)

if __name__ == "__main__":
    bot_start()
    #testando