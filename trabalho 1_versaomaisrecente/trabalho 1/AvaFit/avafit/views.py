from django.shortcuts import render, redirect
import requests
from .models import AvaFit
from .google_fit import ler_passos_hoje, verificar_sono_agora, ler_batimento_medio, get_google_fit_service, obter_nome_utilizador
import os, json, glob
import random # Vamos usar isto para frases variadas
from Adafruit_IO import Client, Data
from .exportar_dados import guardar_dados_google_fit
import datetime
import time
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout



# --- FUNÇÃO DE LOGIN ---
def login_view(request):
    # Para fazer login é exclusivamente com a chave do Google
    if os.path.exists('token.json'):
        return redirect('home') 
    return render(request, 'login.html')

def ligar_google_fit(request):
    try:
        
        get_google_fit_service() 
        
        return redirect('home')
    except Exception as e:
        print(f"Erro ao ligar: {e}")
        return redirect('login')

def home(request):
    if not os.path.exists('token.json'):
        return redirect('login')
    buddy, created = AvaFit.objects.get_or_create(id=1)
    _, passos_ultima_hora = ler_passos_hoje()


    return render(request, 'home.html', {'buddy': buddy,'passos_ultima_hora': passos_ultima_hora})



# caluco da saúde
def calcular_indice_saude(passos, bpm, a_dormir, meta, limite):
    if a_dormir:
        return 100
    if passos < limite and bpm < 70:
        return (passos / meta) * 100
    if passos < meta and 70 <= bpm < 85:
        return ((passos / meta) * 100) + 10
    return (passos / meta) * 100


def atualizar_dados(request):

    
    # Obter o histórico do dia todo 
    passos_dia, bpm_dia, sono_dia, hora_inicio = obter_historico_dia_completo()
    
    
    # Enviar dados para o Adafruit (Histórico completo: Passos, BPM e Sono)
    sincronizar_tudo_adafruit(passos_dia, bpm_dia, sono_dia, hora_inicio)
    
    
    # Guardar o ficheiro local 
    try:
        caminho_ficheiro = guardar_dados_google_fit()
        print(f"Backup criado com sucesso em {caminho_ficheiro}")
    except Exception as e:
        print(f"Erro no backup: {e}")

    # 1. Obter dados (Total do dia e última hora)
    passos_totais, passos_ultima_hora = ler_passos_hoje()
    esta_a_dormir = verificar_sono_agora()
    
    buddy = AvaFit.objects.get(id=1)
    buddy.passos_hoje = passos_totais
    batimento_medio = ler_batimento_medio()
    # Prevenção de erro: se o Google Fit não enviar batimento (None), assumimos 0
    batimento_atual = batimento_medio if batimento_medio else 0
    META_HORARIA = 250
    LIMITE_SEDENTARISMO = 50 
    buddy.saude=0
    

    # --- MOTOR DE REGRAS INTELIGENTE ---

    # 1. Dados Ausentes / Desconectado
    if passos_ultima_hora == 0 and batimento_atual == 0 and not esta_a_dormir:
        buddy.saude = 50 # Nível médio para mostrar o avatar neutro em vez de crítico
        contexto_sedentario = 4

    else:
        # Chamamos a nossa função auxiliar! Muito mais limpo!
        buddy.saude = calcular_indice_saude(passos_ultima_hora, batimento_atual, esta_a_dormir, META_HORARIA, LIMITE_SEDENTARISMO)
        
        if esta_a_dormir: contexto_sedentario = 3
        elif passos_ultima_hora < LIMITE_SEDENTARISMO and batimento_atual < 70: contexto_sedentario = 0
        elif passos_ultima_hora < META_HORARIA and 70 <= batimento_atual < 85: contexto_sedentario = 1
        else: contexto_sedentario = 2

    buddy.saude = int(max(0, min(100, buddy.saude)))

    # 2. Lógica de Emoções
    frases = {
        0: ["Atenção: Detetei falta de movimento. Vamos alongar?", "Estás parado há 1 hora! O teu relógio não engana...", "Sinto-me lenta... Precisamos de circular esse sangue!"],
        1: ["Bom começo, mas a meta ainda está longe!", "Ainda temos caminho pela frente. Vamos a isso?", "Que tal uma caminhada de 5 minutos agora?"],
        2: ["Incrível! Moveste-te bem na última hora!", "Uau! Sinto a energia a fluir!", "Excelente trabalho de equipa entre ti e o relógio!"],
        3: ["Dorme Bem Pookie"],
        4: ["A AvaFit perdeu o sinal do teu relógio. Conecta-te à internet para nos voltarmos a ver 😊"]
    }

    buddy.estado = random.choice(frases[contexto_sedentario])
    buddy.save()



        # ----- INTEGRAÇÃO DIRETA COM O MAKE.COM -----
    webhook_url = 'https://hook.eu1.make.com/ay5kf7xc6t95b6hyxl0oul6pd85m0lfy'

    # Se a saúde for maior ou igual a 80 (Reforço Positivo)
    if buddy.saude >= 80:
        dados = {
            "saude": buddy.saude,
            "mensagem": "Excelente trabalho! I like to move it, move it! 🎉"
        }
        requests.post(webhook_url, json=dados)

    # Se a saúde for menor ou igual a 20 (Alerta de Sedentarismo)
    elif buddy.saude <= 20:
        dados = {
            "saude": buddy.saude,
            "mensagem": "Au Au, leva me a passear! 🚨"
        }
        requests.post(webhook_url, json=dados)
    
    print(f"Total Dia: {passos_totais} | Última Hora: {passos_ultima_hora} | Saúde Final: {buddy.saude}%, Sono: {esta_a_dormir}, Batimento Médio: {batimento_medio}")
    
    return render(request, 'home.html', {
        'buddy': buddy, 
        'contexto_sedentario': contexto_sedentario, 
        'esta_a_dormir': esta_a_dormir,
        'passos_ultima_hora': passos_ultima_hora, 
        'batimento_medio': int(batimento_medio) if batimento_medio else 0,
        'acabou_de_sincronizar': True,
        
    })


def ver_stats(request):
    if not os.path.exists('token.json'):
        return redirect('login')
    buddy = AvaFit.objects.get(id=1)

    # NOME PERSONALIZADO DO USER
    # Tenta ir buscar o nome da conta Google que fez login
    nome_pessoa = obter_nome_utilizador()

    # 1. Procurar o JSON mais recente
    list_of_files = glob.glob('data_imports/*.json')

    # Variáveis por defeito (caso o ficheiro não exista)
    historico_dados = []
    total_json = 0
    passos_stats, bpm_stats, sono_stats, saude_stats = [], [], [], []
    bpm_medio = 0
    horas_sono = 0
    minutos_sono = 0
    labels = ["00h", "03h", "06h", "09h", "12h", "15h", "18h", "21h"]
    
    if list_of_files:
        latest_file = max(list_of_files, key=os.path.getctime)
        with open(latest_file, 'r') as f:
            dados = json.load(f)

            historico_dados = dados.get('registos', [])
            total_json = dados.get('total_passos_dia', 0)

            # --- Informação para os gráficos ---
            META_3H = 750
            LIMITE_SEDENTARISMO_3H = 150
            #Percorre os registos e cria as listas para o Chart.js
            for reg in historico_dados:
                # 1. LER OS VALORES DESTE BLOCO PRIMEIRO
                p = reg.get('passos', 0)
                b = reg.get('bpm', 0)
                s = reg.get('sono', 0)
                
                # 2. ADICIONAR ÀS LISTAS
                passos_stats.append(p)
                bpm_stats.append(b)
                sono_stats.append(s)
                
                
                saude_lida = reg.get('saude')
                
                if saude_lida is not None:
                    saude_stats.append(saude_lida)
                else:
                    # Se o json for antigo usa a função calcular_indice_saude
                    saude_calc = calcular_indice_saude(p, b, s == 1, META_3H, LIMITE_SEDENTARISMO_3H)
                    saude_final = int(max(0, min(100, saude_calc)))
                    saude_stats.append(saude_final)
                
            # --- CÁLCULO DA MÉDIA DO BPM ---
            # Filtramos os zeros para a média ser real (só conta quando há batimento)
            bpm_validos = [b for b in bpm_stats if b > 0]
            if bpm_validos:
                bpm_medio = int(sum(bpm_validos) / len(bpm_validos))
                
            # --- CÁLCULO DO SONO ---
            # Como cada registo de sono equivale a um bloco de 3 horas:
            # Multiplicamos os blocos de sono por 3 para ter o total de horas
            horas_sono = sum(sono_stats) * 3


    # 3. Enviar TUDO para o HTML
    return render(request, 'stats.html', {
        'buddy': buddy, 
        'historico': historico_dados,
        'total_passos': total_json,
        
        # As novas variáveis para a Interface:
        'nome_utilizador': nome_pessoa,
        'bpm_medio': bpm_medio,
        'horas_sono': horas_sono,
        'minutos_sono': minutos_sono,
        
        # As listas para desenhar o gráfico interativo:
        'passos_stats': passos_stats,
        'bpm_stats': bpm_stats,
        'sono_stats': sono_stats,
        'saude_stats': saude_stats,
        'labels': labels
    })

def ver_config(request):
    if not os.path.exists('token.json'):
        return redirect('login')
    buddy = AvaFit.objects.get(id=1)
    # Verifica se o utilizador está ligado (se o ficheiro token existe)
    esta_ligado = os.path.exists('token.json')
    return render(request, 'config.html', {'buddy': buddy, 'esta_ligado': esta_ligado})


def logout_google(request):
    if os.path.exists('token.json'):
        os.remove('token.json')
    
    logout(request)

    return redirect('login')



def obter_historico_dia_completo():
    service = get_google_fit_service()
    agora = datetime.datetime.now()
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_ms = int(inicio_dia.timestamp() * 1000)

    # Início para as SESSÕES (Recuamos 14 horas para apanhar o sono de ontem à noite)
    # Isto garante que se a pessoa adormeceu às 22h de ontem, a sessão é encontrada.
    inicio_sono = inicio_dia - datetime.timedelta(hours=14)
    start_sessao_ms = int(inicio_sono.timestamp() * 1000)

    end_ms = int(agora.timestamp() * 1000)

    # 1. Pedir Passos (Soma por hora)
    res_passos = service.users().dataset().aggregate(userId='me', body={
        "aggregateBy": [{"dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"}],
        "bucketByTime": {"durationMillis": 10800000},
        "startTimeMillis": start_ms, "endTimeMillis": end_ms
    }).execute()

    # 2. Pedir Batimento (Média por hora)
    res_bpm = service.users().dataset().aggregate(userId='me', body={
        "aggregateBy": [{"dataSourceId": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"}],
        "bucketByTime": {"durationMillis": 10800000},
        "startTimeMillis": start_ms, "endTimeMillis": end_ms
    }).execute()

    # 3. Pedir Sono (Segmentos de sono no período)
    res_sono = service.users().sessions().list(
        userId='me',
        startTime=datetime.datetime.fromtimestamp(start_sessao_ms/1000.0).isoformat() + 'Z',
        endTime=datetime.datetime.fromtimestamp(end_ms/1000.0).isoformat() + 'Z'
    ).execute()


    
    sessions = res_sono.get('session', [])
    

    # 4. Processar os dados para listas
    buckets_passos = []
    buckets_bpm = []
    buckets_sono = []

    
    # Usamos o índice 'i' para aceder aos resultados dos agregados de passos/bpm
    for i, h in enumerate(range(0, 24, 3)):
        hora_teste = inicio_dia + datetime.timedelta(hours=h)
        if hora_teste > agora: 
            break

        
        # --- Processar Sono ---
        dormir = 0
        for s in sessions:
            
            if s.get('activityType') == 72:
                s_start = datetime.datetime.fromtimestamp(int(s['startTimeMillis']) / 1000.0)
                s_end = datetime.datetime.fromtimestamp(int(s['endTimeMillis']) / 1000.0)
                if s_start <= hora_teste <= s_end:
                    dormir = 1
                    break
        buckets_sono.append(dormir)

        # --- Processar Passos (Segurança de índice) ---
        val_passos = 0
        try:
            b = res_passos['bucket'][i]
            if b['dataset'][0]['point']:
                val_passos = b['dataset'][0]['point'][0]['value'][0].get('intVal', 0)
        except (IndexError, KeyError): pass

        #  ---  FILTRO DE RUÍDO INTELIGENTE --- 
        # Se detetamos sono profundo neste bloco, qualquer passo registado é falso.
        # Forçamos o valor a 0 antes de adicionar à lista final.
        if dormir == 1:
            val_passos = 0
        buckets_passos.append(val_passos)

        # --- Processar BPM (formato fpVal/intVal) ---
        val_bpm = 0
        try:
            b = res_bpm['bucket'][i]
            if b['dataset'][0]['point']:
                ponto = b['dataset'][0]['point'][0]['value'][0]
                val_bpm = ponto.get('fpVal') or ponto.get('intVal') or 0
        except (IndexError, KeyError): pass
        buckets_bpm.append(int(val_bpm))

    return buckets_passos, buckets_bpm, buckets_sono, inicio_dia


def sincronizar_tudo_adafruit(lista_passos, lista_bpm,lista_sono, hora_inicial):
    aio = Client('trabalho_ambientes', 'aio_JIqc06k79bwc41RuqDh2wNrAeYIA')
    tempo_do_balde = hora_inicial

    # Constantes do Motor de Regras (para o balde de 3h)
    META_3H = 750  # 250 passos * 3 horas
    LIMITE_SEDENTARISMO_3H = 150 # 50 passos * 3 horas

    for i in range(len(lista_passos)):
        try:
            # 1. Obter valores do balde atual
            p_val = int(lista_passos[i])
            b_val = int(lista_bpm[i])
            s_val = int(lista_sono[i])

            # --- CÁLCULO DA SAÚDE  ----------
            saude_calculada = calcular_indice_saude(p_val, b_val, s_val == 1, META_3H, LIMITE_SEDENTARISMO_3H)
            saude_final = int(max(0, min(100, saude_calculada)))
            

            # 1. Formatar a data para o Adafruit (ISO 8601 com 'Z' no fim)
            data_iso = tempo_do_balde.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # . Criar os pacotes de dados
            pacote_passos = Data(value=str(p_val), created_at=data_iso)
            pacote_bpm = Data(value=str(b_val), created_at=data_iso)
            pacote_sono = Data(value=str(s_val), created_at=data_iso)
            pacote_saude = Data(value=str(saude_final), created_at=data_iso)
           
            # 4. Enviar
            aio.create_data('passos', pacote_passos) 
            aio.create_data('batimento', pacote_bpm)
            aio.create_data('sono', pacote_sono)
            aio.create_data('saude', pacote_saude)

            
            print(f"Sincronizando {tempo_do_balde.hour}:00 -> Passos: {p_val}, BPM: {b_val}, Sono: {s_val}, Saúde: {saude_final}%")

            # Pausa de 1 segundo por causa do servidor do Adafruit
            time.sleep(1.5)

        except Exception as e:
            print(f"Erro na sincronização horária: {e}")
        
        tempo_do_balde += datetime.timedelta(hours=3)


def exportar_pdf(request):
    # 1. Procurar o JSON mais recente 
    list_of_files = glob.glob('data_imports/*.json')
    if not list_of_files:
        return HttpResponse("Ainda não existem dados para exportar.")
    
    latest_file = max(list_of_files, key=os.path.getctime)
    with open(latest_file, 'r') as f:
        dados = json.load(f)

    # 2. Configurar o Response do PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Relatorio_AvaFit_{dados["data_importacao"][:10]}.pdf"'

    # 3. Desenhar o PDF
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Título e Cabeçalho
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, height - 50, "Relatório de Saúde AvaFit")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 80, f"Data da Importação: {dados['data_importacao']}")
    p.drawString(100, height - 100, f"Total de Passos no Dia: {dados['total_passos_dia']}")
    p.line(100, height - 110, 500, height - 110)

    # Tabela de Dados
    y = height - 150
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, y, "Hora")
    p.drawString(200, y, "Passos")
    p.drawString(300, y, "BPM")
    p.drawString(400, y, "Estado")
    
    p.setFont("Helvetica", 10)
    for reg in dados.get('registos', []):
        y -= 25
        p.drawString(100, y, reg['timestamp'].split(' ')[1])
        p.drawString(200, y, str(reg['passos']))
        p.drawString(300, y, str(reg['bpm']))
        p.drawString(400, y, "A dormir" if reg['sono'] == 1 else "Ativo")
        
        
        if y < 50: p.showPage(); y = height - 50

    p.showPage()
    p.save()
    return response

