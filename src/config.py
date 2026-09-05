import os
from pathlib import Path
from dotenv import load_dotenv
import static_ffmpeg

# Define o caminho da RAIZ do projeto (onde fica o .env)
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / ".cache"
ENV_PATH = BASE_DIR / ".env"

# Força o carregamento do arquivo .env
load_dotenv(dotenv_path=ENV_PATH)

# Configura FFmpeg
static_ffmpeg.add_paths()

# Lendo as variáveis
TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Configurações do yt-dlp e FFmpeg
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "extractor_args": {"youtube": {"player_client": "web"}}
}

YTDL_FLAT_OPTIONS = {
    "extract_flat": "in_playlist",
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": True
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}