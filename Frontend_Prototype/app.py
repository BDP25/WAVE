from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta
from frontend_agregator import get_clusters_per_date, get_min_date

app = Flask(__name__)

@app.route("/api/clusters")
def api_clusters():
    try:
        datum = request.args.get("datum")
        if not datum:
            return jsonify({"error": "Kein Datum angegeben"}), 400
        clusters = get_clusters_per_date(datum)
        return jsonify(clusters)
    except Exception as e:
        print(f"Fehler in api_clusters: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route("/")
def index():
    #three days ago
    max_date = datetime.now().date() - timedelta(days=2)
    min_date = get_min_date()
    return render_template("index.html", vorgestern=max_date, min_date=min_date)




if __name__ == "__main__":
    app.run(debug=True)

