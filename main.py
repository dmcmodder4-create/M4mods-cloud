import os
import logging
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiohttp import web
import aiohttp  # <-- ADICIONE ISSO: Precisamos do client do aiohttp para chamar sua API

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

# URL do seu site principal (Cérebro)
SITE_API_URL = "https://m4mods.com/api/cloud/get-telegram-id"

# Inicia o Cliente
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- SISTEMA DE DOWNLOAD OTIMIZADO E HÍBRIDO ---
async def handle_stream(request):
    try:
        # Pega o que vier na URL (pode ser o ID '534' ou o nome 'youtube-mod.apk')
        parametro = request.match_info.get('id_or_name')
        msg_id = None
        nome_arquivo_banco = None
        
        # --- ROTEADOR INTELIGENTE ---
        if parametro.isdigit():
            # É LINK ANTIGO! (Ex: /dl/534)
            msg_id = int(parametro)
            logger.info(f"Link legado detectado. Usando ID direto: {msg_id}")
        else:
            # É LINK NOVO! (Ex: /dl/youtube-v12.43-mod.apk)
            logger.info(f"Link novo. Consultando API do M4Mods para: {parametro}")
            
            # Faz a requisição GET na API que você acabou de criar no Flask
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SITE_API_URL}/{parametro}") as resp:
                    if resp.status == 200:
                        dados = await resp.json()
                        msg_id = int(dados.get('msg_id'))
                        nome_arquivo_banco = dados.get('filename')
                    else:
                        logger.error(f"Erro ao consultar M4Mods. Status: {resp.status}")
                        return web.Response(text="Arquivo não encontrado no sistema M4Mods.", status=404)

        if not msg_id:
            return web.Response(text="ID não processado.", status=400)

        # Busca a mensagem no Telegram (Metadados apenas, é rápido)
        message = await client.get_messages(CHANNEL_ID, ids=msg_id)

        if not message or not message.media:
            return web.Response(text="Mídia não encontrada no Telegram.", status=404)

        # Define o nome: Se veio do banco (link novo) usa ele, senão pega do Telegram
        file_name = nome_arquivo_banco or message.file.name or f"mod_{msg_id}.apk"
        file_size = message.file.size

        # --- DICA DE OURO: MATA O BUG DO .BIN NO TELEGRAM WEBVIEW ---
        if file_name.endswith('.apk'):
            mime_type = "application/vnd.android.package-archive"
        else:
            mime_type = message.file.mime_type or "application/octet-stream"

        # --- LÓGICA DE RANGE (RESUME SUPPORT) ---
        range_header = request.headers.get("Range")
        start = 0
        end = file_size - 1
        
        if range_header:
            try:
                matches = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if matches:
                    start = int(matches.group(1))
                    if matches.group(2):
                        end = int(matches.group(2))
            except Exception as e:
                logger.error(f"Erro ao processar range: {e}")

        if start >= file_size:
             return web.Response(status=416)

        chunk_length = end - start + 1
        logger.info(f"Streaming {file_name}: Bytes {start}-{end} (Total: {file_size})")

        headers = {
            'Content-Type': mime_type,
            'Content-Disposition': f'attachment; filename="{file_name}"',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(chunk_length),
            'Content-Range': f'bytes {start}-{end}/{file_size}'
        }

        status_code = 206 if range_header else 200
        response = web.StreamResponse(status=status_code, reason='OK', headers=headers)
        await response.prepare(request)

        # --- DOWNLOAD VIA TELETHON COM OFFSET ---
        async for chunk in client.iter_download(
            message.media, 
            offset=start, 
            request_size=128 * 1024 
        ):
            if start + len(chunk) > end + 1:
                chunk = chunk[:end - start + 1]
            
            await response.write(chunk)
            
            start += len(chunk)
            if start > end:
                break

        return response

    except Exception as e:
        logger.error(f"ERRO no download: {e}")
        return web.StreamResponse(status=500)

# --- SISTEMA ANTI-AMNÉSIA E ROTA DE PING ---
async def keep_alive(request):
    return web.Response(text="Servidor Online e Pronto!")

async def on_startup(app):
    print(">>> CONECTANDO AO TELEGRAM...")
    await client.start()
    print(">>> SERVIDOR DE STREAMING INICIADO!")

app = web.Application()
app.on_startup.append(on_startup)
app.router.add_get('/', keep_alive)

# --- ATENÇÃO AQUI: MUDAMOS A ROTA PARA ACEITAR NOME OU ID ---
app.router.add_get('/dl/{id_or_name}', handle_stream)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, port=port)
