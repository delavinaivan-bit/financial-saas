# app.py
from flask import Flask, render_template, request
import traceback
import tu_script

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_url = request.form.get("url", "").strip()
        transcript_text = request.form.get("transcript", "").strip()
        modo = request.form.get("modo", "0")

        try:
            if transcript_text:
                # Usar transcripción proporcionada por el usuario
                informe = tu_script.generar_informe_financiero_desde_texto(transcript_text, modo)
            elif video_url:
                # Intentar con URL (solo para entornos que no estén bloqueados)
                informe = tu_script.generar_informe_financiero(video_url, modo)
            else:
                return "<h2>Error: Debes pegar una URL o una transcripción.</h2>"

            return render_template("result.html", informe=informe)

        except Exception as e:
            error_detalles = traceback.format_exc()
            print("❌ ERROR COMPLETO EN RENDER:\n", error_detalles)
            return f"<h2>Error al procesar:</h2><pre>{str(e)}</pre>"

    return render_template("index.html")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
