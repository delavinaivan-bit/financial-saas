# app.py
from flask import Flask, render_template, request
import traceback
import tu_script  # Importa tu script corregido

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_url = request.form["url"]
        modo = request.form.get("modo", "0")
        try:
            informe = tu_script.generar_informe_financiero(video_url, modo)
            return render_template("result.html", informe=informe)
        except Exception as e:
            # Imprime el error COMPLETO en los logs de Render
            error_detalles = traceback.format_exc()
            print("❌ ERROR COMPLETO EN RENDER:\n", error_detalles)
            return f"<h2>Error al procesar el video:</h2><pre>{error_detalles}</pre>"
    return render_template("index.html")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))  # Render usa PORT=10000 por defecto
    app.run(host="0.0.0.0", port=port)
