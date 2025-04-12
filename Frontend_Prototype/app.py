from flask import Flask, request, jsonify
from frontend_agregator import get_clusters_per_date  # falls es in einer separaten Datei ist

app = Flask(__name__)

@app.route("/api/clusters")
def api_clusters():
    try:
        datum = request.args.get("datum")
        print(f"Empfangenes Datum: {datum}")  # Debug-Ausgabe
        if not datum:
            return jsonify({"error": "Kein Datum angegeben"}), 400
        clusters = get_clusters_per_date(datum)
        print(f"Zurückgegebene Cluster: {clusters}")  # Debug-Ausgabe
        return jsonify(clusters)
    except Exception as e:
        print(f"Fehler in api_clusters: {str(e)}")
        return jsonify({"error": str(e)}), 500

from flask import request, jsonify, render_template

from datetime import datetime, timedelta

@app.route("/")
def index():
    vorgestern = datetime.now().date() - timedelta(days=2)
    # TODO
    min_date = "2023-05-06"  # implementierst du selbst
    return render_template("index.html", vorgestern=vorgestern, min_date=min_date)




if __name__ == "__main__":
    app.run(debug=True)
