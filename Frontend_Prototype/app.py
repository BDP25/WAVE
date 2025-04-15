from flask import Flask, jsonify, render_template, request
from frontend_agregator import get_clusters_per_date, get_min_max_date
from db_utils import get_article_history_by_title
from db_utils import db_params, redis_params
from vis_text_diff import visualize_wiki_versions_with_deletions

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
        article_title = "Nintendo"
        if not article_title:
            return jsonify({"error": "Kein Artikel angegeben"}), 400
        history = get_article_history_by_title(article_title)
        return jsonify(history)
    except Exception as e:
        print(f"Fehler in api_article_history: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/visualize", methods=["GET"])
def api_visualize():
    try:
        # Get parameters from the request
        article_id = request.args.get("article_id")
        start_revid = int(request.args.get("start_revid"))
        end_revid = int(request.args.get("end_revid"))
        print("Article ID:", article_id)
        print("Start Revid:", start_revid)
        print("End Revid:", end_revid)
        # TODO delete after Testing
        article_id = 50810




        print(article_id, start_revid, end_revid)

        # Validate parameters
        if not article_id or not start_revid or not end_revid:
            return jsonify({"error": "Missing required parameters"}), 400

        # Call the visualization function
        html = visualize_wiki_versions_with_deletions(
            article_id=article_id,
            start_revid=start_revid,
            end_revid=end_revid,
            word_level=True,
            verbose=False,
            db_config=db_params,
            redis_config=redis_params,
            show_revision_info=False
        )

        print(html)

        # Return the HTML as a response
        return jsonify({"html": html})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

