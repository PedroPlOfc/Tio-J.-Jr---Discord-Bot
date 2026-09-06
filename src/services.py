import re
import json
import urllib.request
import urllib.parse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

from .config import SPOTIFY_ID, SPOTIFY_SECRET, YTDL_OPTIONS, YTDL_FLAT_OPTIONS

# Configuração do Spotipy (API oficial do Spotify)
sp = None
if SPOTIFY_ID and SPOTIFY_SECRET:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_ID,
            client_secret=SPOTIFY_SECRET
        ))
    except Exception as e:
        print(f"[SPOTIFY INIT ERROR]: {e}")

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
ytdl_flat = yt_dlp.YoutubeDL(YTDL_FLAT_OPTIONS)

def extrair_buscas_spotify(url):
    itens = []
    print(f"\n--- PROCESSANDO LINK SPOTIFY: {url} ---")
    
    # Limpa parâmetros extras (?si=...)
    url_limpa = url.split("?")[0]
    
    match_track = re.search(r'track[/:]([a-zA-Z0-9]+)', url_limpa)
    match_playlist = re.search(r'playlist[/:]([a-zA-Z0-9]+)', url_limpa)
    match_album = re.search(r'album[/:]([a-zA-Z0-9]+)', url_limpa)

    # 1. TENTATIVA VIA API OFICIAL (SPOTIPY)
    if sp:
        try:
            if match_track:
                track = sp.track(match_track.group(1))
                if track and 'name' in track:
                    artista = track['artists'][0]['name'] if track.get('artists') else ""
                    nome = f"{track['name']} {artista}".strip()
                    itens.append({
                        "titulo": nome,
                        "busca": f"ytsearch1:{nome}" # CORRIGIDO: Prefixo força busca no YouTube
                    })

            elif match_playlist:
                playlist_id = match_playlist.group(1)
                print(f"[SPOTIFY API] Buscando Playlist ID: {playlist_id}")
                
                results = sp.playlist_items(playlist_id)
                while results and results.get('items'):
                    for item in results.get('items', []):
                        if not item or not item.get('track'):
                            continue
                        track = item['track']
                        if track.get('name'):
                            artista = track['artists'][0]['name'] if track.get('artists') else ""
                            nome = f"{track['name']} {artista}".strip()
                            itens.append({
                                "titulo": nome, 
                                "busca": f"ytsearch1:{nome}" # CORRIGIDO: Adicionado ytsearch1:
                            })
                    
                    if results.get('next'):
                        results = sp.next(results)
                    else:
                        results = None

            elif match_album:
                album_id = match_album.group(1)
                results = sp.album_tracks(album_id)
                while results and results.get('items'):
                    for track in results.get('items', []):
                        if track and track.get('name'):
                            artista = track['artists'][0]['name'] if track.get('artists') else ""
                            nome = f"{track['name']} {artista}".strip()
                            itens.append({
                                "titulo": nome, 
                                "busca": f"ytsearch1:{nome}" # CORRIGIDO: Adicionado ytsearch1:
                            })
                    if results.get('next'):
                        results = sp.next(results)
                    else:
                        results = None

        except Exception as e:
            print(f"[SPOTIFY API ERROR] Erro na API do Spotify: {e}")

    # 2. PLANO B (FALLBACK OEMBED / SCRAPING): Se a API oficial retornou 0 faixas
    if not itens and match_playlist:
        print("[SPOTIFY FALLBACK] API retornou 0. Ativando extrator oEmbed/Embed HTML...")
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
                            nome_completo = f"{title} {subtitle}".strip()
                            itens.append({
                                "titulo": nome_completo, 
                                "busca": f"ytsearch1:{nome_completo}" # CORRIGIDO: Adicionado ytsearch1:
                            })
                
                if not itens:
                    titles = re.findall(r'"title":"([^"]+)","subtitle":"([^"]+)"', html)
                    for title, subtitle in titles:
                        nome_completo = f"{title} {subtitle}".strip()
                        if not any(x['titulo'] == nome_completo for x in itens):
                            itens.append({
                                "titulo": nome_completo, 
                                "busca": f"ytsearch1:{nome_completo}" # CORRIGIDO: Adicionado ytsearch1:
                            })

        except Exception as e_embed:
            print(f"[SPOTIFY EMBED ERROR] Falha no extrator Embed: {e_embed}")

    print(f"[SPOTIFY RESULTADO] Total de {len(itens)} músicas prontas para a fila.")
    return itens

def extrair_buscas_youtube_mix(url):
    try:
        data = ytdl_flat.extract_info(url, download=False)
        itens = []
        if 'entries' in data:
            for entry in data['entries']:
                if entry:
                    titulo = entry.get('title', 'Música do YouTube')
                    link = entry.get('url') or entry.get('webpage_url') or titulo
                    itens.append({"titulo": titulo, "busca": link})
        return itens if itens else [{"titulo": url, "busca": url}]
    except Exception as e:
        print(f"Erro YouTube Mix: {e}")
        return [{"titulo": url, "busca": url}]