# app.py
from flask import Flask, render_template, request, redirect, url_for
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
                informe = tu_script.generar_informe_financiero_desde_texto(transcript_text, modo)
            elif video_url:
                informe = tu_script.generar_informe_financiero(video_url, modo)
            else:
                return "<h2>Error: Debes pegar una URL o una transcripción.</h2>"

            # Guardar informe en la sesión (para reenviarlo en el email)
            # o en este ejemplo lo pasamos al template
            return render_template("result.html", informe=informe)

        except Exception as e:
            error_detalles = traceback.format_exc()
            print("❌ ERROR COMPLETO EN RENDER:\n", error_detalles)
            return f"<h2>Error al procesar:</h2><pre>{str(e)}</pre>"

    return render_template("index.html")


@app.route("/send_email", methods=["POST"])
def send_email():
    try:
        destinatario = request.form.get("email")
        informe = request.form.get("informe")

        if not destinatario or not informe:
            return "<h2>Error: falta email o informe.</h2>"

        tu_script.enviar_email(
            destinatario=destinatario,
            asunto="Tu informe financiero",
            cuerpo=informe
        )

        return f"<h2>✅ Informe enviado a {destinatario}</h2>"

    except Exception as e:
        error_detalles = traceback.format_exc()
        print("❌ ERROR EN EMAIL:\n", error_detalles)
        return f"<h2>Error al enviar email:</h2><pre>{str(e)}</pre>"


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
