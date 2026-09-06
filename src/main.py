import os
import asyncio
from pathlib import Path
import discord
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import static_ffmpeg
import re
import urllib.request
import json
static_ffmpeg.add_paths()

# Importa as configurações ajustadas do seu config.py
from .config import TOKEN, SPOTIFY_ID, SPOTIFY_SECRET, YTDL_OPTIONS, YTDL_FLAT_OPTIONS, FFMPEG_OPTIONS

# Configuração do Spotify
sp = None
if SPOTIFY_ID and SPOTIFY_SECRET:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_ID,
            client_secret=SPOTIFY_SECRET
        ))
    except Exception as e:
        print(f"[SPOTIFY INIT ERROR]: {e}")

# Dicionário global para armazenar a fila de músicas por servidor (guild)
queues = {}

def extrair_buscas_spotify(url):
    """Converte links do Spotify (faixas, playlists ou álbuns) em lista de buscas no YouTube"""
    buscas = []
    
    # Extrai o ID e tipo da URL
    url_limpa = url.split("?")[0]
    match_track = re.search(r'track[/:]([a-zA-Z0-9]+)', url_limpa)
    match_playlist = re.search(r'playlist[/:]([a-zA-Z0-9]+)', url_limpa)
    match_album = re.search(r'album[/:]([a-zA-Z0-9]+)', url_limpa)

    # 1. TENTATIVA VIA API OFICIAL (SPOTIPY)
    if sp:
        try:
            if match_track:
                track_info = sp.track(match_track.group(1))
                if track_info and 'name' in track_info:
                    nome = track_info['name']
                    artista = track_info['artists'][0]['name'] if track_info.get('artists') else ""
                    buscas.append(f"ytsearch1:{nome} {artista}")

            elif match_playlist:
                # Usa playlist_items garantindo tratamento
                results = sp.playlist_items(match_playlist.group(1))
                while results and results.get('items'):
                    for item in results.get('items', []):
                        track = item.get('track')
                        if track and track.get('name'):
                            nome = track['name']
                            artista = track['artists'][0]['name'] if track.get('artists') else ""
                            buscas.append(f"ytsearch1:{nome} {artista}")
                    
                    results = sp.next(results) if results.get('next') else None

            elif match_album:
                results = sp.album_tracks(match_album.group(1))
                while results and results.get('items'):
                    for track in results.get('items', []):
                        if track and track.get('name'):
                            nome = track['name']
                            artista = track['artists'][0]['name'] if track.get('artists') else ""
                            buscas.append(f"ytsearch1:{nome} {artista}")
                    
                    results = sp.next(results) if results.get('next') else None

        except Exception as e:
            print(f"[SPOTIFY API ERROR] Falha na API (Status 401 ou permissão): {e}")

    # 2. PLANO B (EMBED SCRAPING): Executado se a API falhar (ex: erro 401) ou se sp for None
    if not buscas and match_playlist:
        print("[SPOTIFY FALLBACK] API indisponível ou 401. Extraindo via Embed HTML...")
        try:
            embed_url = f"https://open.spotify.com/embed/playlist/{match_playlist.group(1)}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            req = urllib.request.Request(embed_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
                match_json = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', html)
                
                if match_json:
                    data = json.loads(match_json.group(1))
                    track_list = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {}).get('trackList', [])
                    for t in track_list:
                        title = t.get('title', '')
                        subtitle = t.get('subtitle', '')
                        if title:
                            buscas.append(f"ytsearch1:{title} {subtitle}")
        except Exception as e_embed:
            print(f"[SPOTIFY EMBED ERROR]: {e_embed}")

    return buscas

def extrair_buscas_youtube_mix(url, ytdl_flat):
    """Extrai os links ou títulos de todos os vídeos presentes em um Mix/Playlist do YouTube"""
    try:
        data = ytdl_flat.extract_info(url, download=False)
        buscas = []
        if 'entries' in data:
            for entry in data['entries']:
                if entry:
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

    # Utiliza as opções centralizadas do config.py
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
    ytdl_flat = yt_dlp.YoutubeDL(YTDL_FLAT_OPTIONS)

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
                        player = discord.FFmpegPCMAudio(url_audio, executable="ffmpeg.exe", **FFMPEG_OPTIONS)
                    except Exception:
                        player = discord.FFmpegPCMAudio(url_audio, **FFMPEG_OPTIONS)

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

        if message.content.startswith("!play"):
            if not message.author.voice:
                await message.channel.send("Entra no canal de voz para tocar a música.")
                return

            voice_channel = message.author.voice.channel
            partes = message.content.split(" ", 1)
            
            if len(partes) < 2 or not partes[1].strip():
                await message.channel.send("Digite a música. Ex: `!play Linkin Park Numb`")
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
                
                if not buscas:
                    await message.channel.send("❌ Não foi possível extrair faixas deste link do Spotify.")
                    return

            # 3. BUSCA DE TEXTO OU VÍDEO ÚNICO DO YOUTUBE
            else:
                buscas = [f"ytsearch1:{entrada}" if not entrada.startswith("http") else entrada]

            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client:
                voice_client = await voice_channel.connect()

            # SE JÁ ESTIVER TOCANDO: Adiciona todas as faixas diretamente na fila
            if voice_client.is_playing() or voice_client.is_paused():
                queues[guild_id].extend(buscas)
                if len(buscas) > 1:
                    await message.channel.send(f"📑 Lista adicionada à fila! (**{len(buscas)} músicas** adicionadas)")
                else:
                    await message.channel.send(f"📝 Adicionado à fila: **{buscas[0].replace('ytsearch1:', '')}**")
            
            # SE NÃO ESTIVER TOCANDO: Toca a primeira faixa e joga o resto na fila
            else:
                primeira = buscas[0]
                if len(buscas) > 1:
                    queues[guild_id].extend(buscas[1:])
                    await message.channel.send(f"📑 Tocando a 1ª faixa e adicionando **{len(buscas)-1} músicas** à fila.")

                await message.channel.send(f"🔍 Buscando por: **{primeira.replace('ytsearch1:', '')}**...")
                
                try:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(primeira, download=False))
                    if 'entries' in data:
                        data = data['entries'][0]

                    url_audio = data['url']
                    titulo = data.get('title', 'Música')

                    try:
                        player = discord.FFmpegPCMAudio(url_audio, executable="ffmpeg.exe", **FFMPEG_OPTIONS)
                    except Exception:
                        player = discord.FFmpegPCMAudio(url_audio, **FFMPEG_OPTIONS)

                    voice_client.play(player, after=lambda e: tocar_proxima(guild_id, voice_client, message.channel, loop))
                    await message.channel.send(f"🎶 Tocando agora: **{titulo}**")
                except Exception as e:
                    await message.channel.send("Erro ao carregar a primeira música. Tentando a próxima da fila...")
                    print(f"Erro no yt-dlp: {e}")
                    tocar_proxima(guild_id, voice_client, message.channel, loop)

        # Comando !skip
        elif message.content.startswith("!skip"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                voice_client.stop()
                await message.channel.send("⏭️ Música pulada!")
            else:
                await message.channel.send("Não tem nenhuma música tocando no momento.")

        # Comando !queue / !fila
        elif message.content.startswith("!queue") or message.content.startswith("!fila"):
            if guild_id in queues and len(queues[guild_id]) > 0:
                lista_msg = "\n".join([f"{i+1}. {m.replace('ytsearch1:', '')}" for i, m in enumerate(queues[guild_id][:10])])
                sobrou = len(queues[guild_id]) - 10
                msg_extra = f"\n... e mais {sobrou} músicas na fila." if sobrou > 0 else ""
                await message.channel.send(f"📋 **Fila Atual ({len(queues[guild_id])} músicas):**\n```\n{lista_msg}{msg_extra}\n```")
            else:
                await message.channel.send("A fila está vazia no momento!")

        # Comando !stop / !leave
        elif message.content.startswith("!stop") or message.content.startswith("!leave"):
            queues[guild_id] = []
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_client.disconnect()
                await message.channel.send("Fila limpa e bot desconectado do canal de voz.")

    bot.run(TOKEN)

if __name__ == "__main__":
    bot_start()