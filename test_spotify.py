from src.config import SPOTIFY_ID, SPOTIFY_SECRET, CACHE_PATH
from src.services import sp

print("=== VERIFICAÇÃO DE CREDENCIAIS ===")
print(f"1. SPOTIFY_CLIENT_ID lido: {SPOTIFY_ID}")
print(f"2. SPOTIFY_CLIENT_SECRET lido: {'***' + SPOTIFY_SECRET[-4:] if SPOTIFY_SECRET else 'NÃO ENCONTRADO'}")
print(f"3. Caminho do arquivo .cache: {CACHE_PATH}")

if not SPOTIFY_ID or not SPOTIFY_SECRET:
    print("\n[ERRO] Verifique seu arquivo .env na raiz do projeto! Os nomes das variáveis precisam ser SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET.")
else:
    print("\nTentando conectar ao Spotify...")
    try:
        # Isso ativará o pedido de autorização no terminal se o cache não existir
        user = sp.current_user()
        print(f"\n[SUCESSO] Conectado como: {user['display_name']}")
        print(f"O arquivo .cache foi criado? {CACHE_PATH.exists()}")
    except Exception as e:
        print(f"\n[FALHA DE AUTENTICAÇÃO]: {e}")

# codigo backup do bot, pra ser usado de teste.