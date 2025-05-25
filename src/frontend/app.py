from flask import Flask, jsonify, render_template, request
from frontend_agregator import get_clusters_per_date, get_min_max_date
from db_utils import get_article_history_by_title, get_cluster_summary
from db_utils import db_params, redis_params
from visualisation import (
    visualize_wiki_versions_with_deletions
)
from cache_utils import (
    get_cached_whois_data, cache_whois_data,
    get_cached_visualization, cache_visualization
)
import time
import logging
import socket
import json
from datetime import datetime

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    """
    Render the index page with the minimum and maximum dates from the database.

    Returns:
        str: Rendered HTML template for the index page
    """
    min_date, max_date = get_min_max_date()

    return render_template("index.html", vorgestern=max_date, min_date=min_date)


@app.route("/api/clusters")
def api_clusters():
    """
    API endpoint to retrieve clusters for a specific date.

    Returns:
        JSON: A list of clusters for the specified date or an error message
    """
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
    """
    API endpoint to retrieve the history of a Wikipedia article by its title.

    Returns:
        JSON: The article's revision history or an error message
    """
    try:
        article_title = request.args.get("title")
        # TODO debug
        print(article_title)
        if not article_title:
            return jsonify({"error": "No article specified"}), 400
        history = get_article_history_by_title(article_title)
        return jsonify(history)
    except Exception as e:
        print(f"Error in api_article_history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/cluster_summary")
def api_cluster_summary():
    """
    API endpoint to retrieve a summary text for a specific cluster on a given date.

    Returns:
        JSON: The cluster summary or an error message
    """
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
    """
    API endpoint to generate or retrieve a cached visualization of changes between
    two versions of a Wikipedia article.

    Returns:
        JSON: HTML visualization content and metadata or an error message
    """
    try:
        # Get parameters from the request
        article_id = request.args.get("article_id")
        start_revid = int(request.args.get("start_revid"))
        end_revid = int(request.args.get("end_revid"))

        logger.info(f"Visualization request: article_id={article_id}, start_revid={start_revid}, end_revid={end_revid}")

        # Validate parameters
        if not article_id or not start_revid or not end_revid:
            return jsonify({"error": "Missing required parameters"}), 400

        # Record start time for performance measurement
        start_time = time.time()

        # Check cache first
        cached_html = get_cached_visualization(
            article_id=article_id,
            start_revid=start_revid,
            end_revid=end_revid,
            word_level=True,
            show_revision_info=False
        )

        if cached_html:
            # Cache hit!
            generation_time = time.time() - start_time
            logger.info(f"Visualization returned from cache in {generation_time:.2f} seconds")

            return jsonify({
                "html": cached_html,
                "metadata": {
                    "generation_time": generation_time,
                    "source": "cache"
                }
            })

        # Cache miss - generate visualization
        html = visualize_wiki_versions_with_deletions(
            article_id=article_id,
            start_revid=start_revid,
            end_revid=end_revid,
            word_level=True,
            verbose=True,
            db_config=db_params,
            redis_config=redis_params,
            show_revision_info=False
        )

        # Calculate generation time
        generation_time = time.time() - start_time
        logger.info(f"Visualization generated in {generation_time:.2f} seconds")

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

        # Store in cache if successful
        cache_visualization(
            article_id=article_id,
            start_revid=start_revid,
            end_revid=end_revid,
            html=html,
            word_level=True,
            show_revision_info=False
        )

        logger.info("Visualization HTML generated and cached successfully")

        # Return the HTML as a response with metadata
        return jsonify({
            "html": html,
            "metadata": {
                "generation_time": generation_time,
                "source": "generated"
            }
        })
    except Exception as e:
        error_message = f"Failed to generate visualization: {str(e)}"
        logger.error(f"Error generating visualization: {str(e)}", exc_info=True)
        return jsonify({
            "error": error_message,
            "html": f"<div class='alert alert-danger'><strong>Error:</strong> {error_message}</div>"
        }), 500

@app.route("/api/ip_info", methods=["GET"])
def api_ip_info():
    """
    API endpoint to retrieve information about an IP address from the BTTF Whois service,
    with caching support.

    Returns:
        JSON: IP information data or an error message
    """
    try:
        # Get IP address from the request
        ip_address = request.args.get("ip")

        if not ip_address:
            return jsonify({"error": "No IP address provided"}), 400

        # Get current date in YYYYMMDD format for the query
        current_date = datetime.now().strftime("%Y%m%d")

        # Check cache first
        cached_data = get_cached_whois_data(ip_address, current_date)
        if cached_data:
            return jsonify({
                "ip": ip_address,
                "whois_data": cached_data,
                "info_date": current_date,
                "source": "cache"
            })

        # Cache miss - query the BTTF Whois service
        whois_data = query_bttf_whois(ip_address, current_date)

        if not whois_data:
            return jsonify({
                "ip": ip_address,
                "error": "Unable to retrieve information for this IP address"
            })

        # Cache the successful response
        cache_whois_data(ip_address, current_date, whois_data)

        # Return the data
        return jsonify({
            "ip": ip_address,
            "whois_data": whois_data,
            "info_date": current_date,
            "source": "api"
        })
    except Exception as e:
        logger.error(f"Error fetching IP information: {str(e)}", exc_info=True)
        return jsonify({
            "ip": ip_address if 'ip_address' in locals() else "unknown",
            "error": f"Failed to retrieve IP information: {str(e)}"
        }), 500

def query_bttf_whois(ip_address, date_str):
    """
    Query the BTTF Whois service for information about an IP address.

    Args:
        ip_address (str): IP address to query
        date_str (str): Date in YYYYMMDD format

    Returns:
        dict: Parsed JSON response or None if query failed
    """
    try:
        # Format query for CIDR notation
        if ':' in ip_address:  # IPv6
            query = f"{ip_address}/128 {date_str}"
        else:  # IPv4
            query = f"{ip_address}/32 {date_str}"

        # Connect to the Whois server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)  # 5 second timeout
        s.connect(("bttf-whois.measurement.network", 43))

        # Send the query
        s.sendall(f"{query}\r\n".encode())

        # Receive the response
        response = b""
        while True:
            data = s.recv(1024)
            if not data:
                break
            response += data

        s.close()

        # Parse the JSON response
        if response:
            try:
                # Convert bytes to string
                response_str = response.decode('utf-8').strip()

                # Extract only the JSON part (skip comment lines starting with #)
                json_text = ""
                for line in response_str.split('\n'):
                    if not line.strip().startswith('#'):
                        json_text += line + "\n"

                # Only try to parse if we found non-comment content
                if json_text.strip():
                    logger.info(f"Parsing JSON: {json_text[:100]}...")
                    return json.loads(json_text.strip())
                else:
                    logger.warning("No JSON content found in response")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Problematic content: {response_str[:100]}...")
                return None
        else:
            return None

    except Exception as e:
        logger.error(f"Error querying BTTF Whois service: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)

