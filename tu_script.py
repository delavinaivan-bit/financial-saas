# tu_script.py
import os
import time
import threading
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import date
import openai
import tiktoken
import re

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Añadimos esta función para evitar el error ---
from youtube_transcript_api import YouTubeTranscriptApi

def get_transcript(video_url):
    """
    Extrae el video_id de cualquier URL de YouTube y devuelve la transcripción como texto.
    """
    # Acepta links tipo youtube.com/watch?v=ID o youtu.be/ID
    patrones = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",   # youtube.com/watch?v=VIDEOID
        r"youtu\.be/([a-zA-Z0-9_-]{11})"  # youtu.be/VIDEOID
    ]

    video_id = None
    for patron in patrones:
        match = re.search(patron, video_url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        raise ValueError("URL de YouTube inválida o no se pudo extraer el video_id.")

    # Descarga la transcripción
    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "es"])

    # Une todas las líneas en un solo texto
    texto = " ".join([entry["text"] for entry in transcript])
    return texto


# --- TODO: copias TODO tu código de antes ---
# Movemos la parte de main a una función
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
    anim_thread.join()

    resumen_y_titulos = generar_resumen_y_titulos(articulo)
    texto_final = (
        "### FULL ARTICLE ###\n\n" +
        articulo +
        "\n\n### SUMMARY + TITLES ###\n\n" +
        resumen_y_titulos
    )

    return texto_final
