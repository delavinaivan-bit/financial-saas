from flask import Flask, render_template, request
import tu_script  # importa tu código

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
            return f"Error: {e}"
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
