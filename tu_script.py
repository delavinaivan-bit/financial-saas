# tu_script.py
import os
import time
import threading
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print("⚠️ OpenAI no disponible:", e)
    client = None

# --- FUNCIONES AUXILIARES ---
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

# --- FUNCIÓN PRINCIPAL ---
def generar_informe_financiero_desde_texto(transcripcion, modo="0"):
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

# --- API FLASK ---
app = Flask(__name__)

@app.route("/resumen", methods=["POST"])
def endpoint_resumen():
    data = request.json
    transcripcion = data.get("transcripcion", "")
    modo = data.get("modo", "0")
    resultado = generar_informe_financiero_desde_texto(transcripcion, modo)
    return jsonify({"resumen": resultado})

if __name__ == "__main__":
    # Render necesita que la app escuche en 0.0.0.0
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
