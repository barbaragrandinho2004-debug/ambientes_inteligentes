import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Definir o que queremos ler
SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read',
'https://www.googleapis.com/auth/fitness.sleep.read',
'https://www.googleapis.com/auth/fitness.heart_rate.read',
'https://www.googleapis.com/auth/userinfo.profile']



def get_google_fit_service():
    creds = None
    # O ficheiro token.json guarda o login do google
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Se não houver login ou for inválido, abre o browser
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('fitness', 'v1', credentials=creds)

def obter_nome_utilizador():
    
    
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            # Liga-se ao serviço de "Contas Google" em vez do "Google Fit"
            servico_conta = build('oauth2', 'v2', credentials=creds)
            perfil = servico_conta.userinfo().get().execute()
            
            # Devolve o nome da pessoa (ou um plano B se falhar)
            return perfil.get('name', 'Utilizador AvaFit')
        except Exception as e:
            print(f"Erro ao obter o nome: {e}")
            
    return "Utilizador AvaFit"


def ler_passos_hoje():
    service = get_google_fit_service()
    
    # 1. Definir o intervalo: das 00:00 do dia até AGORA
    agora = datetime.datetime.now()
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # O Google Fit Aggregate usa milissegundos (ms)
    start_time_ms = int(inicio_dia.timestamp() * 1000)
    end_time_ms = int(agora.timestamp() * 1000)
    
    # 2. Configurar o pedido por "fatias" (buckets) de 1 hora
    # 3600000ms = 1 hora
    body = {
        "aggregateBy": [{
            "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        }],
        "bucketByTime": { "durationMillis": 3600000 }, 
        "startTimeMillis": start_time_ms,
        "endTimeMillis": end_time_ms
    }

    try:
        # 3. Pedir os dados agregados
        response = service.users().dataset().aggregate(userId='me', body=body).execute()
        
        total_dia = 0
        passos_ultima_hora = 0
        
        buckets = response.get('bucket', [])
        
        # 4. Percorrer cada hora do dia
        for i, bucket in enumerate(buckets):
            passos_nesta_hora = 0
            for dataset in bucket.get('dataset', []):
                for point in dataset.get('point', []):
                    for value in point.get('value', []):
                        passos_nesta_hora += value.get('intVal', 0)
            
            # Somamos ao total do dia
            total_dia += passos_nesta_hora
            
            # Se for a última fatia (a hora atual), guardamos o valor
            if i == len(buckets) - 1:
                passos_ultima_hora = passos_nesta_hora
        
        # Retornamos os dois valores para a função 'atualizar_dados' usar
        return total_dia, passos_ultima_hora

    except Exception as e:
        print(f"Erro ao ler passos detalhados: {e}")
        return 0, 0


    
def verificar_sono_agora():
    service = get_google_fit_service()
    
    agora = datetime.datetime.now()
    uma_hora_atras = agora - datetime.timedelta(minutes=60)
    
    start_time_ms = int(uma_hora_atras.timestamp() * 1000)
    end_time_ms = int(agora.timestamp() * 1000)

    # Pedir dados de sono 
    body = {
        "aggregateBy": [{
            "dataTypeName": "com.google.sleep.segment"
        }],
        "startTimeMillis": start_time_ms,
        "endTimeMillis": end_time_ms
    }

    try:
        response = service.users().dataset().aggregate(userId='me', body=body).execute()
        
        buckets = response.get('bucket', [])
        for bucket in buckets:
            for dataset in bucket.get('dataset', []):
                if dataset.get('point'):
                    # Se houver pontos de dados aqui, significa que há sono registado
                    return True
        return False
    except Exception as e:
        print(f"Erro ao ler dados de sono: {e}")
        return False

def ler_batimento_medio():
    service = get_google_fit_service()
    
    agora = datetime.datetime.now()
    uma_hora_atras = agora - datetime.timedelta(minutes=60)
    
    start_time_ms = int(uma_hora_atras.timestamp() * 1000)
    end_time_ms = int(agora.timestamp() * 1000)

    # Pedir a MÉDIA do batimento cardíaco
    body = {
        "aggregateBy": [{
            "dataTypeName": "com.google.heart_rate.bpm"
        }],
        "startTimeMillis": start_time_ms,
        "endTimeMillis": end_time_ms,
        "bucketByTime": { "durationMillis": 3600000 } # Bucket de 1 hora
    }

    try:
        response = service.users().dataset().aggregate(userId='me', body=body).execute()
        
        buckets = response.get('bucket', [])
        for bucket in buckets:
            for dataset in bucket.get('dataset', []):
                for point in dataset.get('point', []):
                    # O Google Fit devolve 3 valores no aggregate de HR: [média, max, min]
                    # O primeiro valor (index 0) é a MÉDIA (fpVal)
                    valores = point.get('value', [])
                    if valores:
                        
                        return valores[0].get('fpVal', 0)
        
        return 0 # Caso não existam dados na última hora
    except Exception as e:
        print(f"Erro ao ler batimento cardíaco: {e}")
        return 0