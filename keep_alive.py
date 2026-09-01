##import time
##import requests

# Substitua pela URL real do seu projeto no Render (ex: https://seu-projeto.onrender.com/menu/)
##URL_ALVO = "https://seu-projeto.onrender.com/" 

##INTERVALO_MINUTOS = 10
##intervalo_segundos = INTERVALO_MINUTOS * 60

##print(f"🔄 Script de Keep-Alive iniciado para: {URL_ALVO}")
##print(f"⏱️ Enviando requisição a cada {INTERVALO_MINUTOS} minutos...\n")

##while True:
##    try:
##        resposta = requests.get(URL_ALVO)
##        tempo_atual = time.strftime("%H:%M:%S")
        
##        if resposta.status_code == 200:
##            print(f"[{tempo_atual}] ✅ Sucesso! O site respondeu com status 200 (Acordado).")
##        else:
##            print(f"[{tempo_atual}] ⚠️ Alerta: O site respondeu com o status {resposta.status_code}.")
            
##    except Exception as e:
##        tempo_atual = time.strftime("%H:%M:%S")
##        print(f"[{tempo_atual}] ❌ Erro ao tentar acessar o site: {e}")
        
    # Aguarda o tempo definido antes da próxima requisição
##    time.sleep(intervalo_segundos)