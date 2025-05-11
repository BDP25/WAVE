import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for, render_template, Blueprint, Response, stream_with_context
import docker
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger  # <-- new import
import datetime
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import json
from utils import execute_docker_command, monitor_docker_events, stream_docker_command
import re  # added for regex matching

# Load environment variables
DOMAIN = os.getenv('DOMAIN', 'localhost:5000')
APPLICATION_ROOT = os.getenv('APPLICATION_ROOT', '/admin')

# Initialize Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static',
            static_url_path=f'{APPLICATION_ROOT}/static')


# New queue blueprint on a separate Flask instance for port 5025
queue_bp = Blueprint('queue_bp', __name__)

@queue_bp.route('/command', methods=['POST'])
def add_queue_command():
    data = request.json
    command_text = data.get('command', '')
    if command_text.startswith("collect-date"):
        # Expected format: "collect-date <date>"
        parts = command_text.split()
        if len(parts) < 2:
            return jsonify(error="Date is required"), 400
        date_value = parts[1]
        container_name = f"data-collector-{date_value}"
        docker_command = f"run --rm --env-file .env data_collector --date {date_value}"
        with date_lock:
            date_queue.append({'docker_command': docker_command, 'container_name': container_name})
        return jsonify(message="Date collector task queued"), 200
    elif command_text.startswith("collect-history"):
        # Expected format: "collect-history <title>"
        parts = command_text.split(maxsplit=1)
        if len(parts) < 2:
            return jsonify(error="Title is required"), 400
        title = parts[1]
        # Format container name: lowercase and replace spaces with hyphens
        formatted_title = title.lower().replace(' ', '-')
        container_name = f"history-collector-{formatted_title}"
        docker_command = f'run --rm --env-file .env history-collector --title "{title}" --lang "de"'
        with history_lock:
            history_queue.append({'docker_command': docker_command, 'container_name': container_name})
        return jsonify(message="History collector task queued"), 200
    else:
        return jsonify(error="Unknown command"), 400

# Create a new Flask instance for the queue endpoint
queue_app = Flask(__name__)
queue_app.register_blueprint(queue_bp)

app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# Apply ProxyFix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure application root
app.config['APPLICATION_ROOT'] = APPLICATION_ROOT

# Initialize Docker client and scheduler
client = docker.from_env()
scheduler = BackgroundScheduler()
scheduler.start()

# Store jobs for reference
scheduled_jobs = {}
chained_containers = {}

# Store command presets
command_presets = []
presets_file = os.path.join("/data", "command_presets.json")
# Ensure the /data directory exists
os.makedirs(os.path.dirname(presets_file), exist_ok=True)

env_folder = os.path.join("/data", "env")

# Load presets from file if exists
try:
    if os.path.exists(presets_file):
        with open(presets_file, 'r') as f:
            command_presets = json.load(f)
except Exception as e:
    print(f"Error loading presets: {e}")
    command_presets = []

# Add persistent jobs file path
SCHEDULED_JOBS_FILE = os.path.join("/data", "scheduled_jobs.json")

# New helper to persist scheduled jobs
def persist_scheduled_jobs():
    persistent_jobs = {}
    for job_id, info in scheduled_jobs.items():
        persistent_jobs[job_id] = {
            'job_id': job_id,
            'docker_command': info['docker_command'],
            'chain_command': info.get('chain_command', ''),
            'cron': info.get('cron'),
            'job_name': info.get('job_name'),
            'run_at': info.get('run_at'),
            'env_vars': info.get('env_vars')
        }
    try:
        with open(SCHEDULED_JOBS_FILE, 'w') as f:
            json.dump(persistent_jobs, f)
    except Exception as e:
        print(f"Error persisting scheduled jobs: {e}")

# New helper to load and reschedule persisted jobs
def load_scheduled_jobs():
    if os.path.exists(SCHEDULED_JOBS_FILE):
        try:
            with open(SCHEDULED_JOBS_FILE, 'r') as f:
                persistent_jobs = json.load(f)
            for job_id, job_data in persistent_jobs.items():
                if job_data.get('cron'):
                    trigger = CronTrigger.from_crontab(job_data['cron'])
                elif job_data.get('run_at'):
                    run_at = datetime.datetime.fromisoformat(job_data['run_at'])
                    if run_at < datetime.datetime.now():
                        run_at = datetime.datetime.now()
                    trigger = run_at
                else:
                    continue
                job = scheduler.add_job(
                    execute_docker_command,
                    trigger=trigger,
                    args=[client, job_id, job_data['docker_command'], job_data.get('chain_command', ''), job_data.get('env_vars')]
                )
                scheduled_jobs[job_id] = {
                    'job': job,
                    'next_run': trigger.__str__(),
                    'docker_command': job_data['docker_command'],
                    'cron': job_data.get('cron'),
                    'job_name': job_data.get('job_name'),
                    'run_at': job_data.get('run_at'),
                    'env_vars': job_data.get('env_vars')
                }
        except Exception as e:
            print(f"Error loading scheduled jobs: {e}")

# Define blueprint for API endpoints
bp = Blueprint('bp', __name__, static_folder='static')

@bp.before_request
def require_login():
    # Allow login and logout routes to be accessed without login
    if request.endpoint in ('bp.login', 'bp.logout', 'bp.static'):
        return
    if not session.get('logged_in'):
        return redirect(url_for('bp.login'))

@bp.route('/api/collect-date', methods=['POST'])
def collect_date():
    data = request.json
    date = data.get('date')
    if not date:
        return jsonify(error="Date is required"), 400
    formatted_date = date.replace('/', '-')
    container_name = f"data-collector-{date}"
    # Updated command to include --network wave_default
    docker_command = f'run --rm --env-file .env --name {container_name} --network wave_default data_collector --date "{date}"'
    with date_lock:
        date_queue.append({'docker_command': docker_command, 'container_name': container_name})
    return jsonify(message="Date collector task queued"), 200

@bp.route('/api/presets', methods=['GET'])
def get_presets():
    return jsonify(presets=command_presets)

@bp.route('/api/presets', methods=['POST'])
def add_preset():
    data = request.json
    name = data.get('name', '')
    command = data.get('command', '')

    if not name or not command:
        return jsonify(error="Name and command are required"), 400

    preset_id = str(uuid.uuid4())
    preset = {
        'id': preset_id,
        'name': name,
        'command': command
    }

    command_presets.append(preset)

    # Save to file
    try:
        with open(presets_file, 'w') as f:
            json.dump(command_presets, f)
    except Exception as e:
        print(f"Error saving presets: {e}")

    return jsonify(message="Preset added", preset=preset)

@bp.route('/api/presets/<preset_id>', methods=['DELETE'])
def delete_preset(preset_id):
    global command_presets

    original_length = len(command_presets)
    command_presets = [p for p in command_presets if p.get('id') != preset_id]

    if len(command_presets) < original_length:
        # Save to file
        try:
            with open(presets_file, 'w') as f:
                json.dump(command_presets, f)
        except Exception as e:
            print(f"Error saving presets: {e}")

        return jsonify(message="Preset deleted")

    return jsonify(error="Preset not found"), 404

@bp.route('/api/presets/execute/<preset_id>', methods=['POST'])
def execute_preset(preset_id):
    preset = next((p for p in command_presets if p.get('id') == preset_id), None)

    if not preset:
        return jsonify(error="Preset not found"), 404

    try:
        result = execute_docker_command(client, None, preset['command'])
        return jsonify(message=f"Preset '{preset['name']}' executed", result=result)
    except Exception as e:
        return jsonify(error=str(e)), 500

@bp.route('/api/containers', methods=['GET'])
def get_containers():
    containers_info = []
    for container in client.containers.list():
        start = container.attrs["State"].get("StartedAt")
        try:
            if start:
                # Remove trailing 'Z', split fractional part, limit to 6 digits for microseconds
                if '.' in start:
                    sec, frac_z = start.split('.', 1)
                    frac = frac_z.rstrip("Z")[:6]
                    start_time = datetime.datetime.fromisoformat(f"{sec}.{frac}+00:00")
                else:
                    start_time = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                uptime_delta = datetime.datetime.now(datetime.timezone.utc) - start_time
                uptime = str(uptime_delta).split('.')[0]  # remove microseconds display
            else:
                uptime = "unknown"
        except Exception:
            uptime = "unknown"
        containers_info.append({'name': container.name, 'uptime': uptime})
    return jsonify(containers=containers_info)

@bp.route('/api/schedule', methods=['POST'])
def schedule_job():
    data = request.json
    docker_command = data.get('docker_command', '')
    chain_command = data.get('chain_command')
    delay = data.get('delay', 0)
    cron_expr = data.get('cron')  # new field for cron expression
    job_name = data.get('job_name', 'Unnamed Job')
    env_file = data.get('env_file')
    env_vars = None
    if env_file:
        file_path = os.path.join(env_folder, env_file)
        if os.path.exists(file_path):
            try:
                env_vars = {}
                with open(file_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            except Exception as e:
                return jsonify(error=f"Failed to load env file: {str(e)}"), 500
        else:
            return jsonify(error="Env file not found"), 404

    if not docker_command:
        return jsonify(error="docker_command is required"), 400

    # Modify command for data_collector/history-collector if necessary
    if docker_command.startswith('run --rm --env-file .env data_collector') and "--name" not in docker_command:
        m = re.search(r'--date\s+"([^"]+)"', docker_command)
        date_str = m.group(1) if m else "latest"
        container_name = f"data-collector-{date_str}"
        docker_command = docker_command.replace("data_collector", f'--name {container_name} --network wave_default data_collector', 1)
    elif docker_command.startswith('run --rm --env-file .env history-collector') and "--name" not in docker_command:
        m = re.search(r'--title\s+"([^"]+)"', docker_command)
        title = m.group(1) if m else "unknown"
        formatted_title = title.lower().replace(' ', '-')
        container_name = f"history-collector-{formatted_title}"
        docker_command = docker_command.replace("history-collector", f'--name {container_name} --network wave_default history-collector', 1)

    job_id = str(uuid.uuid4())
    if cron_expr:
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
            run_at_str = None
        except Exception as e:
            return jsonify(error=f"Invalid cron expression: {e}"), 400
    else:
        run_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        trigger = run_time  # use date trigger
        run_at_str = run_time.isoformat()

    job = scheduler.add_job(
        execute_docker_command,
        trigger=trigger,
        args=[client, job_id, docker_command, chain_command, env_vars]
    )
    scheduled_jobs[job_id] = {
        'job': job,
        'next_run': trigger.__str__(),
        'docker_command': docker_command,
        'cron': cron_expr if cron_expr else None,
        'job_name': job_name,
        'run_at': run_at_str,
        'env_vars': env_vars
    }
    persist_scheduled_jobs()
    return jsonify(message="Job scheduled", job_id=job_id, run_at=trigger.__str__())

@bp.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    if job_id in scheduled_jobs:
        job_info = scheduled_jobs[job_id]
        job_info['job'].remove()
        del scheduled_jobs[job_id]
        persist_scheduled_jobs()
        return jsonify(message="Job deleted")
    return jsonify(error="Job not found"), 404

@bp.route('/api/env', methods=['POST'])
def create_env_file():
    data = request.json
    filename = data.get('filename', '.env')
    content = data.get('content', '')
    if not content:
        return jsonify(error="Environment content is required"), 400
    os.makedirs(env_folder, exist_ok=True)
    file_path = os.path.join(env_folder, filename)
    try:
        with open(file_path, 'w') as f:
            f.write(content)
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(message=f"{filename} created successfully", path=file_path)

@bp.route('/api/env', methods=['GET'])
def read_env_file():
    filename = request.args.get('filename', '.env')
    file_path = os.path.join(env_folder, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            return jsonify(content=content)
        except Exception as e:
            return jsonify(error=str(e)), 500
    return jsonify(error="Env file not found"), 404

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == os.getenv('PASSWORD_ORCHESTRATOR'):
            session['logged_in'] = True
            return redirect(url_for('bp.index'))
        else:
            return render_template('login.html', error="Invalid password"), 401
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('bp.login'))

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/api/queue-status', methods=['GET'])
def queue_status():
    global date_queue, date_running_jobs, date_completed, history_queue, history_running_jobs, history_completed
    return jsonify({
        "date": {
            "stats": f"Pending: {len(date_queue)} Running: {len(date_running_jobs)} Completed: {len(date_completed)}",
            "running_jobs": date_running_jobs,
            "upcoming_jobs": date_queue
        },
        "history": {
            "stats": f"Pending: {len(history_queue)} Running: {len(history_running_jobs)} Completed: {len(history_completed)}",
            "running_jobs": history_running_jobs,
            "upcoming_jobs": history_queue
        }
    })

@bp.route('/api/jobs', methods=['GET'])
def get_jobs():
    jobs_list = []
    for job_id, job_info in scheduled_jobs.items():
        jobs_list.append({
            'id': job_id,
            'docker_command': job_info.get('docker_command', ''),
            'next_run': job_info.get('next_run', ''),
            'chain_command': job_info.get('chain_command', ''),
            'job_name': job_info.get('job_name', 'Unnamed Job')  # include job name
        })
    return jsonify(jobs=jobs_list)

# New global queues and concurrency controls
date_queue = []
history_queue = []
max_concurrency = 3
date_lock = threading.Lock()
history_lock = threading.Lock()
date_running = 0
history_running = 0
# New running job lists
date_running_jobs = []
history_running_jobs = []
# Completed jobs lists remain unchanged
date_completed = []
history_completed = []
MAX_COMPLETED_HISTORY = 100

# New functions to process each queue
def process_date_queue():
    global date_running, date_running_jobs
    while True:
        with date_lock:
            if date_queue and date_running < max_concurrency:
                task = date_queue.pop(0)
                date_running += 1
                date_running_jobs.append(task)
            else:
                task = None
        if task:
            def run_task(task=task):
                global date_running, date_running_jobs
                cmd = task['docker_command']
                print(f"Processing date task: {cmd}")
                result = execute_docker_command(client, None, cmd)
                with date_lock:
                    date_running -= 1
                    if task in date_running_jobs:
                        date_running_jobs.remove(task)
                    date_completed.append({
                        'docker_command': cmd,
                        'result': result,
                        'completed_at': datetime.datetime.now().isoformat()
                    })
                    if len(date_completed) > MAX_COMPLETED_HISTORY:
                        date_completed.pop(0)
            threading.Thread(target=run_task, daemon=True).start()
        time.sleep(1)

def process_history_queue():
    global history_running, history_running_jobs
    while True:
        with history_lock:
            if history_queue and history_running < max_concurrency:
                task = history_queue.pop(0)
                history_running += 1
                history_running_jobs.append(task)
            else:
                task = None
        if task:
            def run_task(task=task):
                global history_running, history_running_jobs
                cmd = task['docker_command']
                print(f"Processing history task: {cmd}")
                result = execute_docker_command(client, None, cmd)
                with history_lock:
                    history_running -= 1
                    if task in history_running_jobs:
                        history_running_jobs.remove(task)
                    history_completed.append({
                        'docker_command': cmd,
                        'result': result,
                        'completed_at': datetime.datetime.now().isoformat()
                    })
                    if len(history_completed) > MAX_COMPLETED_HISTORY:
                        history_completed.pop(0)
            threading.Thread(target=run_task, daemon=True).start()
        time.sleep(1)

# Add new endpoint to get detailed completed jobs
@bp.route('/api/completed-jobs', methods=['GET'])
def get_completed_jobs():
    job_type = request.args.get('type', 'all')
    limit = int(request.args.get('limit', MAX_COMPLETED_HISTORY))

    if job_type == 'date':
        # Return only date jobs, most recent first
        return jsonify({"jobs": date_completed[-limit:][::-1]})
    elif job_type == 'history':
        # Return only history jobs, most recent first
        return jsonify({"jobs": history_completed[-limit:][::-1]})
    else:
        # Return all jobs, most recent first from both queues
        all_jobs = []
        for job in date_completed[-limit:]:
            job_copy = job.copy()
            job_copy['type'] = 'date'
            all_jobs.append(job_copy)
        for job in history_completed[-limit:]:
            job_copy = job.copy()
            job_copy['type'] = 'history'
            all_jobs.append(job_copy)
        # Sort all jobs by completed_at, descending
        all_jobs.sort(key=lambda x: x['completed_at'], reverse=True)
        return jsonify({"jobs": all_jobs[:limit]})

# Register blueprint with application root prefix
app.register_blueprint(bp, url_prefix=APPLICATION_ROOT)
# Start Docker event monitoring using utils function
threading.Thread(target=monitor_docker_events, args=(client, chained_containers), daemon=True).start()

if __name__ == "__main__":
    # Start queue processing threads
    threading.Thread(target=process_date_queue, daemon=True).start()
    threading.Thread(target=process_history_queue, daemon=True).start()

    # Start the queue endpoint on port 5025 in a separate thread
    def run_queue_app():
        queue_app.run(host='0.0.0.0', port=5025, debug=False, use_reloader=False)
    threading.Thread(target=run_queue_app, daemon=True).start()

    # Load persisted scheduled jobs before starting
    load_scheduled_jobs()
    print(f"Flask app running on {DOMAIN} with prefix '{APPLICATION_ROOT}'")
    app.run(host='0.0.0.0', port=5050, debug=False)
