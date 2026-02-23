import os
import logging
import re  # Importei para processar o header Range
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiohttp import web

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

# Inicia o Cliente
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- SISTEMA DE DOWNLOAD OTIMIZADO ---
async def handle_stream(request):
    try:
        msg_id = int(request.match_info.get('id'))
        
        # Busca a mensagem (Metadados apenas, é rápido)
        message = await client.get_messages(CHANNEL_ID, ids=msg_id)

        if not message or not message.media:
            return web.Response(text="Arquivo não encontrado.", status=404)

        file_name = message.file.name or f"mod_{msg_id}.apk"
        file_size = message.file.size
        mime_type = message.file.mime_type or "application/octet-stream"

        # --- LÓGICA DE RANGE (RESUME SUPPORT) ---
        range_header = request.headers.get("Range")
        start = 0
        end = file_size - 1
        
        # Se o navegador pediu um trecho específico (Resume)
        if range_header:
            # Exemplo de header: bytes=500- (do 500 até o fim)
            try:
                matches = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if matches:
                    start = int(matches.group(1))
                    if matches.group(2):
                        end = int(matches.group(2))
            except Exception as e:
                logger.error(f"Erro ao processar range: {e}")
                # Se falhar, segue o download normal do zero

        # Garante que não passamos do tamanho real
        if start >= file_size:
             return web.Response(status=416) # Range Not Satisfiable

        chunk_length = end - start + 1
        
        logger.info(f"Streaming {file_name}: Bytes {start}-{end} (Total: {file_size})")

        headers = {
            'Content-Type': mime_type,
            'Content-Disposition': f'attachment; filename="{file_name}"',
            'Accept-Ranges': 'bytes',  # Avisa o navegador que suportamos resume
            'Content-Length': str(chunk_length),
            'Content-Range': f'bytes {start}-{end}/{file_size}'
        }

        # Se for resume (start > 0), status é 206. Se for full, 200.
        status_code = 206 if range_header else 200

        response = web.StreamResponse(status=status_code, reason='OK', headers=headers)
        await response.prepare(request)

        # --- DOWNLOAD VIA TELETHON COM OFFSET ---
        # request_size: Pega blocos maiores (128KB) para usar menos CPU/IO
        # offset: O pulo do gato. Começa exatamente onde o user parou.
        async for chunk in client.iter_download(
            message.media, 
            offset=start, 
            request_size=128 * 1024 
        ):
            # Se o chunk passar do 'end' solicitado (raro, mas possível), cortamos
            if start + len(chunk) > end + 1:
                chunk = chunk[:end - start + 1]
            
            await response.write(chunk)
            
            start += len(chunk)
            if start > end:
                break

        return response

    except Exception as e:
        logger.error(f"ERRO no download {msg_id}: {e}")
        # Se a conexão já estiver aberta, não dá pra mudar o status code, 
        # então apenas logamos. O navegador vai perceber que parou.
        return web.StreamResponse(status=500)

# --- SISTEMA ANTI-AMNÉSIA E ROTA DE PING ---
async def keep_alive(request):
    return web.Response(text="Servidor Online e Pronto!")

async def on_startup(app):
    print(">>> CONECTANDO AO TELEGRAM...")
    await client.start()
    print(">>> ATUALIZANDO DIALOGS...")
    # Isso aqui é bom só pra garantir que o cache interno do telethon carregue
    async for dialog in client.iter_dialogs(limit=5): 
        pass
    print(">>> SERVIDOR DE STREAMING INICIADO!")

app = web.Application()
app.on_startup.append(on_startup)
app.router.add_get('/', keep_alive)
app.router.add_get('/dl/{id}', handle_stream)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, port=port)
