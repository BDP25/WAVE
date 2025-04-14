from flask import Flask, jsonify, render_template, request
from frontend_agregator import get_clusters_per_date, get_min_max_date
from db_utils import get_article_history_by_title
app = Flask(__name__)


@app.route("/")
def index():

    min_date, max_date = get_min_max_date()
    return render_template("index.html", vorgestern=max_date, min_date=min_date)


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


@app.route("/api/article_history")
def api_article_history():
    try:
        article_title = request.args.get("title")
        # TODO debug
        print(article_title)
        article_title = "Refugiados"
        if not article_title:
            return jsonify({"error": "Kein Artikel angegeben"}), 400
        history = get_article_history_by_title(article_title)
        return jsonify(history)
    except Exception as e:
        print(f"Fehler in api_article_history: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

