# tu_script.py
import os
import time
import threading
import re
import traceback
from dotenv import load_dotenv
import youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi

print("🔍 YouTubeTranscriptApi path:", youtube_transcript_api.__file__)
print("🔍 dir(YouTubeTranscriptApi):", dir(YouTubeTranscriptApi))

import openai
import tiktoken

# Cargar variables de entorno
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Función para extraer transcripción ---
def get_transcript(video_url):
    # Extraer el ID del video
    patrones = [r"(?:v=)([a-zA-Z0-9_-]{11})", r"youtu\.be/([a-zA-Z0-9_-]{11})"]
    video_id = None
    for patron in patrones:
        match = re.search(patron, video_url)
        if match:
            video_id = match.group(1)
            break
    if not video_id:
        raise ValueError("URL de YouTube inválida o no se pudo extraer el video_id.")

    # Usar la API moderna (list_transcripts)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en', 'es']).fetch()
        texto = " ".join([t['text'] for t in transcript])
        return texto
    except Exception as e:
        raise ValueError(f"No se pudo obtener la transcripción: {e}")

# --- Funciones auxiliares (placeholder seguros) ---
def contar_palabras(texto):
    return len(texto.split())

def dividir_transcripcion(texto, max_tokens=5000):
    # Dividir por tamaño aproximado (1 token ≈ 0.75 palabras)
    palabras = texto.split()
    max_palabras = int(max_tokens * 0.75)
    bloques = []
    for i in range(0, len(palabras), max_palabras):
        bloques.append(" ".join(palabras[i:i + max_palabras]))
    return bloques

def llamar_gpt(part_num, total, bloque, prompt_base):
    # Simulación segura (reemplaza con tu lógica real de OpenAI)
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
        return f"[Error en GPT para parte {part_num}: {str(e)}]"

def generar_resumen_y_titulos(articulo):
    try:
        res_prompt = (
            "Resume el siguiente artículo en 3-5 oraciones. "
            "Luego, sugiere 3 títulos atractivos para un blog financiero.\n\n"
            + articulo[:10000]  # límite para evitar tokens excesivos
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": res_prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error al generar resumen: {str(e)}]"

def mostrar_cargando():
    # En Render, no hay terminal interactiva. Solo esperar.
    while not stop_anim.is_set():
        time.sleep(0.5)

# --- Función principal ---
def generar_informe_financiero(video_url, modo="0"):
    global stop_anim
    stop_anim = threading.Event()

    transcripcion = get_transcript(video_url)
    estilo_prompt = (
        "Write an EXTENSIVE blog article in your own expert voice. "
        "Do NOT reference the transcript, speakers, or video. "
        "Avoid quotes, names, or attributions. "
        "Write professional, analytical paragraphs only."
    )

    min_palabras = 1500 if modo == "0" else 6000
    bloques = dividir_transcripcion(transcripcion, max_tokens=5000 if modo == "0" else 3500)

    # Iniciar animación (solo en consola, no visible en Render, pero inofensiva)
    anim_thread = threading.Thread(target=mostrar_cargando)
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

    stop_anim.set()
    anim_thread.join(timeout=1)

    resumen_y_titulos = generar_resumen_y_titulos(articulo)
    texto_final = (
        "### FULL ARTICLE ###\n\n" +
        articulo +
        "\n\n### SUMMARY + TITLES ###\n\n" +
        resumen_y_titulos
    )

    return texto_final
