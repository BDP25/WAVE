from flask import Flask, request, jsonify
import threading, time, uuid, docker

app = Flask(__name__)
docker_client = docker.from_env()

# Queues and running status dictionaries
date_queue = []
history_queue = []
date_running = {}      # job_id: True
history_running = {}   # job_id: True
MAX_CONCURRENT = 3

def process_queue(queue, running_dict, prefix):
    while True:
        if len(running_dict) < MAX_CONCURRENT and queue:
            job = queue.pop(0)
            job_id = job.get('id')
            running_dict[job_id] = True
            def run_job(job, prefix, job_id):
                command = job['command']
                container_name = job.get('container_name', f"{prefix}-{job_id}")
                try:
                    # Naively parse the command: remove leading "run" token.
                    parts = command.split()
                    if parts and parts[0].lower() == "run":
                        parts = parts[1:]
                    if len(parts) < 2:
                        print(f"Job {job_id}: no image specified")
                        return
                    image = parts[1]
                    container_cmd = parts[2:] if len(parts) > 2 else None
                    container = docker_client.containers.run(
                        image,
                        command=container_cmd,
                        name=container_name,
                        detach=True,
                        environment=None,
                        remove=True,
                        network="wave_default"
                    )
                    for log in container.logs(stream=True):
                        print(log.decode("utf-8"))
                    container.wait()
                except Exception as e:
                    print(f"Error in job {job_id}: {e}")
                finally:
                    running_dict.pop(job_id, None)
            threading.Thread(target=run_job, args=(job, prefix, job_id)).start()
        time.sleep(1)

threading.Thread(target=process_queue, args=(date_queue, date_running, "datecollector"), daemon=True).start()
threading.Thread(target=process_queue, args=(history_queue, history_running, "historycollector"), daemon=True).start()

@app.route('/queue/collect-date', methods=['POST'])
def add_date_job():
    data = request.json
    date_val = data.get('date')
    if not date_val:
        return jsonify(error="Date is required"), 400
    job_id = str(uuid.uuid4())
    container_name = f"data-collector-{date_val.strip().replace(' ', '-')}"
    # Updated command to include --network wave_default
    docker_command = f'run --rm --env-file .env --name {container_name} --network wave_default data_collector --date "{date_val}"'
    date_queue.append({'id': job_id, 'command': docker_command, 'container_name': container_name})
    return jsonify(message="Job added to date collector queue", job_id=job_id)

@app.route('/queue/collect-history', methods=['POST'])
def add_history_job():
    data = request.json
    title = data.get('title')
    lang = data.get('lang', 'de')
    if not title:
        return jsonify(error="Title is required"), 400
    job_id = str(uuid.uuid4())
    formatted_title = title.lower().replace(' ', '-')
    container_name = f"history-collector-{formatted_title}"
    # Updated command to include --name and --network wave_default
    docker_command = f'run --rm --env-file .env --name {container_name} --network wave_default history-collector --title "{title}" --lang "{lang}"'
    history_queue.append({'id': job_id, 'command': docker_command, 'container_name': container_name})
    return jsonify(message="Job added to history collector queue", job_id=job_id)

@app.route('/queue/status', methods=['GET'])
def queue_status():
    return jsonify(
        date_queue = [job['id'] for job in date_queue],
        date_running = list(date_running.keys()),
        history_queue = [job['id'] for job in history_queue],
        history_running = list(history_running.keys())
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5025)
