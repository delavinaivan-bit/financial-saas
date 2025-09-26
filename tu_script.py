# tu_script.py
# tu_script.py
import os
import time
import threading
import re
import traceback
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Cliente de OpenAI
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print("⚠️ Error al inicializar OpenAI:", e)
    client = None

# --- Función para extraer transcripción (versión segura) ---
def get_transcript(video_url):
    from youtube_transcript_api import YouTubeTranscriptApi
    import re

    # Extraer ID
    patrones = [r"(?:v=)([a-zA-Z0-9_-]{11})", r"youtu\.be/([a-zA-Z0-9_-]{11})"]
    video_id = None
    for patron in patrones:
        match = re.search(patron, video_url)
        if match:
            video_id = match.group(1)
            break
    if not video_id:
        raise ValueError("URL de YouTube inválida")

    try:
        # ✅ Esta función existe desde la v0.1.0
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en'])
        return " ".join([t['text'] for t in transcript])
    except Exception as e:
        # Intentar con cualquier idioma si falla
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join([t['text'] for t in transcript])
        except Exception as e2:
            raise ValueError(f"Transcripción no disponible: {e2}")

# --- Funciones auxiliares ---
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
        return f"[Error en GPT para parte {part_num}: {str(e)}]"

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
        return f"[Error al generar resumen: {str(e)}]"

def mostrar_cargando():
    # Solo para entornos con terminal; en Render no hace nada visible
    while not getattr(mostrar_cargando, 'stop', False):
        time.sleep(0.5)

# --- Función principal ---
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

    # Animación de carga (inofensiva en Render)
    mostrar_cargando.stop = False
    anim_thread = threading.Thread(target=mostrar_cargando, daemon=True)
    anim_thread.start()

    partes = []
    for i, bloque in enumerate(bloques):
        parte = llamar_gpt(i + 1, len(bloques), bloque, estilo_prompt)
        partes.append(parte)

    articulo = "\n\n".join(partes)

    # Expandir si es necesario
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

    # Detener animación
    mostrar_cargando.stop = True
    if anim_thread.is_alive():
        anim_thread.join(timeout=1)

    resumen_y_titulos = generar_resumen_y_titulos(articulo)
    texto_final = (
        "### FULL ARTICLE ###\n\n" +
        articulo +
        "\n\n### SUMMARY + TITLES ###\n\n" +
        resumen_y_titulos
    )

    return texto_final
