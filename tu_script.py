# tu_script.py
import os
import time
import threading
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import date
import openai
import tiktoken

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Añadimos esta función para evitar el error ---
from youtube_transcript_api import YouTubeTranscriptApi, get_transcript

def get_transcript(video_url):
    # extraer el ID del video de la URL
    if "v=" not in video_url:
        raise ValueError("URL de YouTube inválida")
    video_id = video_url.split("v=")[-1].split("&")[0]
    
    # obtener la transcripción usando el método correcto
    transcript_list = get_transcript(video_id)
    
    # unir en un solo string
    transcript = " ".join([t['text'] for t in transcript_list])
    return transcript


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
