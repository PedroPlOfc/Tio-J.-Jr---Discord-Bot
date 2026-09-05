import asyncio
import discord
from .config import TOKEN, FFMPEG_OPTIONS
from .services import extrair_buscas_spotify, extrair_buscas_youtube_mix, ytdl

queues = {}

def bot_start():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = discord.Client(intents=intents)

    def tocar_proxima(guild_id, voice_client, channel, loop):
        if guild_id in queues and len(queues[guild_id]) > 0:
            proxima = queues[guild_id].pop(0)  # Pega o objeto {"titulo": ..., "busca": ...}
            
            async def carregar_e_tocar():
                await channel.send(f"🔍 Carregando: **{proxima['titulo']}**...")
                try:
                    data = await loop.run_in_executor(
                        None, lambda: ytdl.extract_info(proxima['busca'], download=False)
                    )
                    if 'entries' in data:
                        data = data['entries'][0]

                    url_audio = data['url']
                    titulo_real = data.get('title', proxima['titulo'])

                    player = discord.FFmpegPCMAudio(url_audio, **FFMPEG_OPTIONS)
                    voice_client.play(
                        player, 
                        after=lambda e: tocar_proxima(guild_id, voice_client, channel, loop)
                    )
                    await channel.send(f"🎶 Tocando agora: **{titulo_real}**")
                except Exception as err:
                    await channel.send("Erro ao carregar faixa. Tentando a próxima...")
                    print(f"Erro tocar_proxima: {err}")
                    tocar_proxima(guild_id, voice_client, channel, loop)

            asyncio.run_coroutine_threadsafe(carregar_e_tocar(), loop)
        else:
            asyncio.run_coroutine_threadsafe(channel.send("✅ A fila de músicas terminou!"), loop)

    @bot.event
    async def on_ready():
        print(f"🤖 {bot.user} está online!")

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return

        guild_id = message.guild.id
        if guild_id not in queues:
            queues[guild_id] = []

        # COMANDO !P / !PLAY
        if message.content.startswith("!p ") or message.content == "!p" or message.content.startswith("!play"):
            if not message.author.voice:
                await message.channel.send("Entre num canal de voz primeiro!")
                return

            voice_channel = message.author.voice.channel
            partes = message.content.split(" ", 1)
            
            if len(partes) < 2 or not partes[1].strip():
                await message.channel.send("Digite o nome ou link da música!")
                return

            entrada = partes[1].strip()
            loop = asyncio.get_event_loop()

            if ("youtube.com" in entrada or "youtu.be" in entrada) and ("list=" in entrada):
                await message.channel.send("🌀 Processando Playlist/Mix do YouTube...")
                novas_faixas = await loop.run_in_executor(None, lambda: extrair_buscas_youtube_mix(entrada))
            elif "spotify.com" in entrada:
                await message.channel.send("🟢 Processando Spotify...")
                novas_faixas = await loop.run_in_executor(None, lambda: extrair_buscas_spotify(entrada))

                if not novas_faixas:
                    await message.channel.send("⚠️ Não foi possível carregar o link do Spotify. Verifique se a playlist é pública no perfil ou se é um Mix automático.")
                    return
            else:
                novas_faixas = [{"titulo": entrada, "busca": entrada}]

            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client:
                voice_client = await voice_channel.connect()

            if voice_client.is_playing() or voice_client.is_paused():
                queues[guild_id].extend(novas_faixas)
                await message.channel.send(f"📝 Adicionado à fila: **{len(novas_faixas)} música(s)**")
            else:
                primeira = novas_faixas[0]
                if len(novas_faixas) > 1:
                    queues[guild_id].extend(novas_faixas[1:])

                queues[guild_id].insert(0, primeira)
                tocar_proxima(guild_id, voice_client, message.channel, loop)

        # COMANDO !CLEAR / !LIMPAR (LIMPA A FILA SEM DESCONECTAR)
        elif message.content.startswith("!clear") or message.content.startswith("!limpar"):
            qtd_removida = len(queues[guild_id])
            queues[guild_id] = []
            await message.channel.send(f"🧹 A fila de músicas foi limpa ({qtd_removida} músicas removidas)! A música atual continuará tocando.")

        # COMANDO !PAUSE / !PAUSAR
        elif message.content.startswith("!pause") or message.content.startswith("!pausar"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                await message.channel.send("⏸️ Música pausada!")
            elif voice_client and voice_client.is_paused():
                await message.channel.send("⚠️ A música já está pausada.")
            else:
                await message.channel.send("❌ Nenhuma música está sendo tocada no momento.")

        # COMANDO !RESUME / !DESPAUSAR / !RETOMAR
        elif message.content.startswith("!resume") or message.content.startswith("!despausar") or message.content.startswith("!retomar"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await message.channel.send("▶️ Música retomada!")
            elif voice_client and voice_client.is_playing():
                await message.channel.send("⚠️ A música já está tocando.")
            else:
                await message.channel.send("❌ Nenhuma música está na fila para ser retomada.")

        # COMANDO !QUEUE / !FILA
        elif message.content.startswith("!queue") or message.content.startswith("!fila"):
            if guild_id in queues and len(queues[guild_id]) > 0:
                lista_msg = "\n".join([
                    f"{i+1}. {item['titulo']}" for i, item in enumerate(queues[guild_id][:10])
                ])
                sobrou = len(queues[guild_id]) - 10
                msg_extra = f"\n... e mais {sobrou} música(s)." if sobrou > 0 else ""
                await message.channel.send(f"📋 **Fila Atual ({len(queues[guild_id])} músicas):**\n```\n{lista_msg}{msg_extra}\n```")
            else:
                await message.channel.send("A fila está vazia no momento!")

        # COMANDO !SKIP
        elif message.content.startswith("!skip"):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                voice_client.stop()
                await message.channel.send("⏭️ Música pulada!")

        # COMANDO !STOP / !LEAVE
        elif message.content.startswith("!stop") or message.content.startswith("!leave"):
            queues[guild_id] = []
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_client.disconnect()
                await message.channel.send("Fila limpa e bot desconectado.")

    bot.run(TOKEN)

if __name__ == "__main__":
    bot_start()