import os
import json
import datetime 


def guardar_dados_google_fit():
    # 1. Definir o caminho da pasta 
    folder = 'data_imports'
    
    # Garantia de segurança: Se a pasta não existir, é criada
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"Pasta '{folder}' criada com sucesso.")

    # 2. Obter os dados (Total e a lista de fatias horárias)
    from .views import obter_historico_dia_completo
    passos_dia, bpm_dia, sono_dia, hora_inicio = obter_historico_dia_completo() 
    
    # Criar um nome de ficheiro único com data e hora
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_ficheiro = f'import_{timestamp}.json'
    
    # Unir a pasta ao nome do ficheiro (Caminho completo)
    json_path = os.path.join(folder, nome_ficheiro)
    
    # Criar uma lista detalhada com timestamps
    detalhe_completo = []
    tempo_corrente = hora_inicio
    
    for i in range(len(passos_dia)):
        detalhe_completo.append({
            "timestamp": tempo_corrente.strftime("%Y-%m-%d %H:%M"),
            "passos": passos_dia[i],
            "bpm": bpm_dia[i],
            "sono": sono_dia[i]
        })
        tempo_corrente += datetime.timedelta(hours=3) 

    dados_final = {
        "data_importacao": str(datetime.datetime.now()),
        "total_passos_dia": sum(passos_dia),
        "registos": detalhe_completo 
    }

    # 4. Guardar o ficheiro
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(dados_final, f, indent=4, ensure_ascii=False)
        print(f"JSON guardado em: {json_path}")
    except Exception as e:
        print(f"Erro ao guardar o ficheiro: {e}")

    return json_path