import re
import requests
import sys
from telethon import TelegramClient, events

# --- CONFIGURAÇÕES DO BOT ---
API_ID = 20180148            
API_HASH = "3f34ec99c52a700d689bb2d31d39519b"      
BOT_TOKEN = "8572055021:AAFvcODxhQmxDt1nZmvYG13g073uvrgAtxY"

# --- CONFIGURAÇÕES DO SITE ---
CHANNEL_ID = -1002724406272  
SITE_URL = "https://modder4.com/api/bot/update-mod"
SITE_KEY = "bata_a_cabeca_no_teclado_para_gerar_uma_senha_dific>" 
STREAMER_BASE = "https://cloud4-iff9.onrender.com/dl"

# --- INICIA O CLIENTE ---
client = TelegramClient('bot_carteiro', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

print("🔇 Bot Carteiro (Modo Silencioso) Iniciado! Logs apenas no Painel Admin.")

@client.on(events.NewMessage(chats=CHANNEL_ID))
async def handler(event):
    if event.message.message:
        texto = event.message.message
        
        # Regex que aceita maiúsculas/minúsculas
        match = re.search(r'(?:id|package)[:\s]+([a-zA-Z0-9_.]+)', texto, re.IGNORECASE)
        
        if match:
            # 1. Pega os dados
            package_name = match.group(1).strip().rstrip('.')
            version_code = 0
            
            match_build = re.search(r'(?:build|code|version)[:\s]+(\d+)', texto, re.IGNORECASE)
            if match_build:
                version_code = int(match_build.group(1))
            
            msg_id = event.id
            link_final = f"{STREAMER_BASE}/{msg_id}"
            
            # Limpa o texto para pegar features manuais
            features_limpa = texto
            if match: features_limpa = features_limpa.replace(match.group(0), "")
            if match_build: features_limpa = features_limpa.replace(match_build.group(0), "")
            features_limpa = features_limpa.strip()
            
            # Log apenas no terminal do servidor (pra você saber que ele está vivo)
            print(f"📦 Enviando para o site: {package_name} (Build: {version_code})")

            # 2. Envia para o site (SEM RESPONDER NO TELEGRAM)
            try:
                payload = {
                    "package_name": package_name,
                    "link": link_final,
                    "features": features_limpa,
                    "version_code": version_code
                }
                headers = {"Authorization": SITE_KEY}
                
                # Dispara e esquece (Fire and Forget)
                # O site que se vire para salvar no Log do Banco de Dados
                r = requests.post(SITE_URL, json=payload, headers=headers)
                
                if r.status_code == 200:
                    print(f"✅ Sucesso: {package_name} registrado no painel.")
                else:
                    print(f"❌ Erro Site ({r.status_code}): Verifique /admin/bot-logs")
                    
            except Exception as e:
                print(f"❌ Erro Conexão: {e}")

# Mantém rodando
client.run_until_disconnected()
