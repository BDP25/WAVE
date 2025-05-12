from db_query import test_get_cluster_articles_by_index
from flask import jsonify, request


@app.route('/api/test-articles')
def test_articles():
    date = request.args.get("date")
    cluster = request.args.get("cluster")

    cluster_index = int(cluster)
    result = test_get_cluster_articles_by_index(cluster_index, date)
    return jsonify({"cluster_id": result} if isinstance(result, int) else result)