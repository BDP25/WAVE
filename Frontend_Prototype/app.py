from flask import Flask, jsonify, render_template, request
from frontend_agregator import get_clusters_per_date, get_min_max_date
from db_utils import get_article_history_by_title, get_cluster_summary
from db_utils import db_params, redis_params
from vis_text_div.visualization import visualize_wiki_versions_with_deletions

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
        if not article_title:
            return jsonify({"error": "Kein Artikel angegeben"}), 400
        history = get_article_history_by_title(article_title)
        return jsonify(history)
    except Exception as e:
        print(f"Fehler in api_article_history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/cluster_summary")
def api_cluster_summary():
    try:
        cluster_id = request.args.get("cluster_id")
        date = request.args.get("date")
        print("Cluster ID:", cluster_id)
        print("Date:", date)


        # Convert cluster_id to integer
        try:
            cluster_index = int(cluster_id)
        except ValueError:
            return jsonify({"error": "Cluster ID must be a number"}), 400

        # Call the existing function from db_utils.py
        summary = get_cluster_summary(cluster_index, date)

        # Return the summary along with metadata
        return jsonify({
            "summary": summary
        })
    except Exception as e:
        print(f"Error in api_cluster_summary: {str(e)}")
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

        # Validate parameters
        if not article_id or not start_revid or not end_revid:
            return jsonify({"error": "Missing required parameters"}), 400

        # Call the visualization function
        html = visualize_wiki_versions_with_deletions(
            article_id=article_id,
            start_revid=start_revid,
            end_revid=end_revid,
            word_level=True,
            verbose=True,  # Enable verbose to get more debugging info
            db_config=db_params,
            redis_config=redis_params,
            show_revision_info=False
        )

        # Check if html contains an error message
        if html and ("<div class='alert alert-danger'>" in html or "<div class='alert alert-warning'>" in html):
            # Still return 200 but with the error message in HTML
            return jsonify({"html": html})

        # Check if html is None or empty
        if not html:
            return jsonify({
                "error": "No visualization data available for the selected revisions",
                "html": "<div class='alert alert-danger'>No visualization data available for the selected revisions</div>"
            }), 404

        print("Visualization HTML generated successfully")

        # Return the HTML as a response
        return jsonify({"html": html})
    except Exception as e:
        error_message = f"Failed to generate visualization: {str(e)}"
        print(f"Error generating visualization: {str(e)}")
        return jsonify({
            "error": error_message,
            "html": f"<div class='alert alert-danger'><strong>Error:</strong> {error_message}</div>"
        }), 500

# TODO TESTING
# For testing only, add to your Flask backend
@app.route('/api/test-articles')
def test_articles():
    date = request.args.get("date")
    cluster = request.args.get("cluster")
    cluster_index = int(cluster)


    from Validating_Cluster_helpler.db_query import test_get_cluster_articles_by_index
    result = test_get_cluster_articles_by_index(cluster_index, date)
    return jsonify({"cluster_id": result} if isinstance(result, int) else result)




if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
