from django.shortcuts import render, redirect
from .models import AvaFit
from .google_fit import ler_passos_hoje, verificar_sono_agora, ler_batimento_medio
import os
import random # Vamos usar isto para frases variadas
from Adafruit_IO import Client

def home(request):
    buddy, created = AvaFit.objects.get_or_create(id=1)
    return render(request, 'home.html', {'buddy': buddy})

import random

def atualizar_dados(request):
    # 1. Obter dados (Total do dia e última hora)
    passos_totais, passos_ultima_hora = ler_passos_hoje()
    esta_a_dormir = verificar_sono_agora()
    
    buddy = AvaFit.objects.get(id=1)
    buddy.passos_hoje = passos_totais
    batimento_medio = ler_batimento_medio()
    META_HORARIA = 250
    LIMITE_SEDENTARISMO = 50 
    buddy.saude=0

    

    

    

    # --- MOTOR DE REGRAS INTELIGENTE ---

    if esta_a_dormir:
        # Se está a dormir, ignoramos os passos e mantemos a saúde
        buddy.estado = "Zzz... A AvaFit também está a dormir. Shhh!"
        # Não alteramos a saúde ou damos um pequeno bónus de recuperação
        buddy.saude = min(100, buddy.saude + 2)
        contexto_sedentario = 3 #mudar para contexto de sono


    elif passos_ultima_hora < LIMITE_SEDENTARISMO and batimento_medio < 70:
            buddy.saude = passos_ultima_hora/META_HORARIA * 100
            contexto_sedentario = 0

    elif passos_ultima_hora < META_HORARIA and 70 <= batimento_medio < 85:
        buddy.saude = (passos_ultima_hora/META_HORARIA * 100) + 10 #+ 10 bonus de estar no nivel a seguir, para diferenciar alguem que deu 49 passos e alguem que deu 51
        contexto_sedentario = 1

    else: 
        buddy.saude = passos_ultima_hora/META_HORARIA * 100
        contexto_sedentario = 2


    # 3. Lógica de Emoções (Frases Dinâmicas)
    frases_alerta_sedentario = [
        "Atenção: Detetei falta de movimento. Vamos alongar?",
        "Estás parado há 1 hora! O teu relógio não engana...",
        "Sinto-me lenta... Precisamos de circular esse sangue!"
    ]
    frases_ativas = [
        "Incrível! Moveste-te bem na última hora!",
        "Uau! Sinto a energia a fluir!",
        "Excelente trabalho de equipa entre ti e o relógio!"
    ]
    frases_meta_longe = [
        "Bom começo, mas a meta de 5000 ainda está longe!",
        "Ainda temos caminho pela frente. Vamos a isso?",
        "Que tal uma caminhada de 5 minutos agora?"
    ]
    frases_sono = [
        "Dorme Bem Pookie"]

    # 2. Lógica de Frases baseada APENAS no que aconteceu agora
    if contexto_sedentario == 0:
        buddy.estado = random.choice(frases_alerta_sedentario)
    elif contexto_sedentario == 1:
        buddy.estado = random.choice(frases_meta_longe)
    elif contexto_sedentario == 2:
        buddy.estado = random.choice(frases_ativas)
    elif contexto_sedentario == 3:
        buddy.estado = random.choice(frases_sono)
    

    # 3. Salvaguarda e Gravação
    buddy.saude = max(0, min(100, buddy.saude))
    buddy.save()
    
    # Ligar ao Adafruit (usa a tua Key que está no site deles)
    aio = Client('trabalho_ambientes', 'aio_zjXN24Zl5qPzO2A9TCxy4qyzcUwu')

    dados_para_enviar = {
    'passos': int(passos_ultima_hora),
    'batimento': int(batimento_medio) if batimento_medio else 0,
    'sono': 1 if esta_a_dormir else 0,
    'saude': int(buddy.saude)
    
}
    for nome_feed, valor in dados_para_enviar.items():
        try:
            aio.send(nome_feed, valor)
            print(f"SUCESSO: Enviado {valor} para o feed '{nome_feed}'")
        except Exception as e:
            print(f"ERRO no feed '{nome_feed}': {e}")
    print(f"DEBUG: Total Dia: {passos_totais} | Última Hora: {passos_ultima_hora} | Saúde Final: {buddy.saude}%, Sono: {esta_a_dormir}, Batimento Médio: {batimento_medio}")
    
    return render(request, 'home.html', {'buddy': buddy, 'contexto_sedentario': contexto_sedentario, 'esta_a_dormir': esta_a_dormir})

def ver_stats(request):
    buddy = AvaFit.objects.get(id=1)
    return render(request, 'stats.html', {'buddy': buddy})

def ver_config(request):
    buddy = AvaFit.objects.get(id=1)
    # Verifica se o utilizador está ligado (se o ficheiro token existe)
    esta_ligado = os.path.exists('token.json')
    return render(request, 'config.html', {'buddy': buddy, 'esta_ligado': esta_ligado})

def logout_google(request):
    if os.path.exists('token.json'):
        os.remove('token.json')
    return redirect('config')

def calcular_estado_buddy(buddy, dados_samsung):
    # 1. Verificar se está a dormir (usando o ficheiro 'sleep')
    if esta_a_dormir(dados_samsung['sleep']):
        buddy.estado = "Zzz... A descansar."
        return buddy ##############################3

    # 2. Analisar a última hora (usando 'pedometer step count')
    _,passos_ultima_hora = ler_passos_hoje()
    
    # 3. Analisar batimento (usando 'heart rate')
    batimento_medio = ler_batimento_medio()

    if passos_ultima_hora < 50:
        if batimento_medio < 70: # Valor exemplo para repouso
            buddy.saude -= 10  # Penaliza o sedentarismo
            buddy.estado = "Estás muito parado! Vamos dar um passeio?"
        else:
            buddy.estado = "Pareces focado, mas não te esqueças de alongar!"
    else:
        buddy.saude += 5 # Recompensa o movimento
        buddy.estado = "Boa! Adoro ver-te em movimento."

    # Garantir que a saúde não sai dos limites 0-100
    buddy.saude = max(0, min(100, buddy.saude))
    buddy.save()