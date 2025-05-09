import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for, render_template, Blueprint, Response, stream_with_context
import docker
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import threading
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import json
from utils import execute_docker_command, monitor_docker_events, stream_docker_command

# Load environment variables
DOMAIN = os.getenv('DOMAIN', 'localhost:5000')
APPLICATION_ROOT = os.getenv('APPLICATION_ROOT', '/admin')

# Initialize Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static',
            static_url_path=f'{APPLICATION_ROOT}/static')

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

# Create blueprint with URL prefix
bp = Blueprint('bp', __name__, url_prefix=APPLICATION_ROOT)

@bp.before_request
def require_login():
    # Allow access to login and static routes without authentication
    if request.endpoint in ('bp.login', 'static'):
        return None
    if not session.get('logged_in'):
        return redirect(url_for('bp.login'))

@bp.route('/api/execute', methods=['POST'])
def execute_command_immediately():
    data = request.json
    docker_command = data.get('docker_command', '')
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

    return Response(
        stream_with_context(stream_docker_command(client, None, docker_command, None, env_vars)),
        mimetype='text/plain'
    )

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
    job_id = str(uuid.uuid4())
    run_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
    job = scheduler.add_job(
        execute_docker_command,
        trigger='date',
        run_date=run_time,
        args=[client, job_id, docker_command, chain_command, env_vars]
    )
    scheduled_jobs[job_id] = {'job': job, 'next_run': run_time.isoformat(), 'docker_command': docker_command}
    return jsonify(message="Job scheduled", job_id=job_id, run_at=run_time.isoformat())

@bp.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    if job_id in scheduled_jobs:
        job_info = scheduled_jobs[job_id]
        job_info['job'].remove()
        del scheduled_jobs[job_id]
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

# Register blueprint
app.register_blueprint(bp)

# Start Docker event monitoring using utils function
threading.Thread(target=monitor_docker_events, args=(client, chained_containers), daemon=True).start()

if __name__ == "__main__":
    print(f"Flask app running on {DOMAIN} with prefix '{APPLICATION_ROOT}'")
    app.run(host='0.0.0.0', port=5050, debug=False)
