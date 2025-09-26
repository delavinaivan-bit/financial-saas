# tu_script.py
import os
import time
import threading
import re
import traceback
import requests
from dotenv import load_dotenv

load_dotenv()

# OpenAI
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print("⚠️ OpenAI no disponible:", e)
    client = None

# --- FUNCIÓN: Extraer transcripción usando requests (sin youtube-transcript-api) ---
def get_transcript(video_url):
    # Extraer video_id
    patrones = [r"(?:v=)([a-zA-Z0-9_-]{11})", r"youtu\.be/([a-zA-Z0-9_-]{11})"]
    video_id = None
    for patron in patrones:
        match = re.search(patron, video_url)
        if match:
            video_id = match.group(1)
            break
    if not video_id:
        raise ValueError("URL de YouTube inválida")

    # Paso 1: Obtener la página del video para extraer el `captions` JSON
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36'
    }
    try:
        response = requests.get(f"https://www.youtube.com/watch?v={video_id}", headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"No se pudo acceder al video: {e}")

    # Paso 2: Buscar el JSON de configuración del reproductor
    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?})\s*;', response.text)
    if not match:
        raise ValueError("No se encontró la configuración del reproductor. El video podría ser privado.")

    import json
    try:
        player_response = json.loads(match.group(1))
    except json.JSONDecodeError:
        raise ValueError("Error al analizar la configuración del video.")

    # Paso 3: Buscar subtítulos
    captions = player_response.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
    if not captions:
        raise ValueError("El video no tiene subtítulos públicos (ni automáticos ni manuales).")

    # Preferir subtítulos en español o inglés
    selected_caption = None
    for caption in captions:
        lang = caption.get('languageCode', '')
        if lang in ['es', 'en']:
            selected_caption = caption
            break
    if not selected_caption:
        selected_caption = captions[0]  # tomar el primero

    caption_url = selected_caption['baseUrl']

    # Asegurar formato de texto plano
    caption_url += "&fmt=json3"  # formato JSON limpio

    # Paso 4: Descargar los subtítulos
    try:
        cap_response = requests.get(caption_url, headers=headers, timeout=10)
        cap_response.raise_for_status()
        cap_data = cap_response.json()
    except Exception as e:
        raise ValueError(f"No se pudieron descargar los subtítulos: {e}")

    # Paso 5: Extraer texto
    text_parts = []
    for event in cap_data.get('events', []):
        if 'segs' in event:
            for seg in event['segs']:
                if 'utf8' in seg:
                    text_parts.append(seg['utf8'])
    if not text_parts:
        raise ValueError("Los subtítulos están vacíos o en formato no soportado.")

    return " ".join(text_parts)

# --- Resto del código (sin cambios) ---
def contar_palabras(texto):
    return len(texto.split())

def dividir_transcripcion(texto, max_tokens=5000):
    palabras = texto.split()
    max_palabras = int(max_tokens * 0.75)
    bloques = []
    for i in range(0, len(palabras), max_palabras):
        bloques.append(" ".join(palabras[i:i + max_palabras]))
    return bloques

def llamar_gpt(part_num, total, bloque, prompt_base):
    if client is None:
        return "[Error: OpenAI no configurado]"
    full_prompt = f"{prompt_base}\n\nParte {part_num} de {total}:\n\n{bloque}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": full_prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error en GPT parte {part_num}: {str(e)}]"

def generar_resumen_y_titulos(articulo):
    if client is None:
        return "[Error: OpenAI no configurado]"
    try:
        res_prompt = (
            "Resume el siguiente artículo en 3-5 oraciones. "
            "Luego, sugiere 3 títulos atractivos para un blog financiero.\n\n"
            + articulo[:10000]
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": res_prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error resumen: {str(e)}]"

def mostrar_cargando():
    while not getattr(mostrar_cargando, 'stop', False):
        time.sleep(0.5)

def generar_informe_financiero(video_url, modo="0"):
    try:
        transcripcion = get_transcript(video_url)
    except Exception as e:
        raise ValueError(f"Fallo al obtener transcripción: {e}")

    estilo_prompt = (
        "Write an EXTENSIVE blog article in your own expert voice. "
        "Do NOT reference the transcript, speakers, or video. "
        "Avoid quotes, names, or attributions. "
        "Write professional, analytical paragraphs only."
    )

    min_palabras = 1500 if modo == "0" else 6000
    max_tokens = 5000 if modo == "0" else 3500
    bloques = dividir_transcripcion(transcripcion, max_tokens=max_tokens)

    mostrar_cargando.stop = False
    anim_thread = threading.Thread(target=mostrar_cargando, daemon=True)
    anim_thread.start()

    partes = []
    for i, bloque in enumerate(bloques):
        parte = llamar_gpt(i + 1, len(bloques), bloque, estilo_prompt)
        partes.append(parte)

    articulo = "\n\n".join(partes)

    intentos = 0
    while contar_palabras(articulo) < min_palabras and intentos < 3:
        faltan = min_palabras - contar_palabras(articulo)
        prompt_extra = (
            f"Expand the article with at least {faltan} more words. "
            f"Provide additional sections, examples, and in-depth analysis. "
            f"Do NOT repeat earlier content."
        )
        parte_extra = llamar_gpt("Extra", "Extra", transcripcion, prompt_extra)
        if contar_palabras(parte_extra) < 200:
            intentos += 1
        else:
            partes.append(parte_extra)
            articulo = "\n\n".join(partes)
            intentos = 0

    mostrar_cargando.stop = True
    if anim_thread.is_alive():
        anim_thread.join(timeout=1)

    resumen_y_titulos = generar_resumen_y_titulos(articulo)
    return (
        "### FULL ARTICLE ###\n\n" +
        articulo +
        "\n\n### SUMMARY + TITLES ###\n\n" +
        resumen_y_titulos
    )
