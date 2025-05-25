import uuid
import docker
import datetime
import subprocess
import os
import shlex
import urllib.parse
import re

def sanitize_string(input_string):
    """
    Sanitize a string to create a valid container name.

    Args:
        input_string (str): The input string to sanitize.

    Returns:
        str: A sanitized string suitable for use as a container name.
    """
    if not input_string:
        return "container-" + str(uuid.uuid4())[:8]

    # First decode URL-encoded strings if needed
    try:
        # Check if the string contains URL encoding
        if '%' in input_string:
            decoded = urllib.parse.unquote(input_string)
        else:
            decoded = input_string
    except:
        decoded = input_string

    # Replace specific German characters with ASCII equivalents
    sanitized = decoded.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    sanitized = sanitized.replace('Ä', 'AE').replace('Ö', 'OE').replace('Ü', 'UE')

    # Replace any non-alphanumeric or non-underscore/dash/dot characters with dashes
    sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '-', sanitized)

    # Ensure the name does not start or end with a dash
    sanitized = sanitized.strip('-')

    # Convert to lowercase for consistency
    sanitized = sanitized.lower()

    # Make sure the container name is not empty after sanitization
    if not sanitized or sanitized.isdigit():
        return "container-" + str(uuid.uuid4())[:8]

    return sanitized

def execute_docker_command(client, job_id, docker_command, chain_command=None, env_vars=None, container_name=None):
    """
    Execute a Docker command using the Docker client.

    Args:
        client (docker.DockerClient): The Docker client instance.
        job_id (str): The ID of the job.
        docker_command (str): The Docker command to execute.
        chain_command (str, optional): A command to execute after the main command.
        env_vars (dict, optional): Environment variables for the container.
        container_name (str, optional): The name of the container.

    Returns:
        str: Logs or error message from the executed command.
    """
    print(f"Executing docker command: {docker_command}")
    try:
        parts = shlex.split(docker_command)
        # Remove leading "docker" token if provided
        if parts and parts[0].lower() == "docker":
            parts = parts[1:]
        if not parts:
            print("Empty docker command")
            return "Empty docker command"
        action = parts[0]

        # Process flags: --env-file, --rm, and --name
        local_env_vars = env_vars  # allow preset passed env_vars to take precedence if provided
        rm_flag = False
        # Loop over a copy of parts to remove flag tokens
        cleaned_parts = []
        skip_next = False
        for i, token in enumerate(parts):
            if skip_next:
                skip_next = False
                continue
            if token == "--env-file":
                if i + 1 < len(parts):
                    env_filename = parts[i+1]
                    env_path = os.path.join("/data", "env", env_filename)
                    if os.path.exists(env_path):
                        try:
                            local_env_vars = {}
                            with open(env_path) as f:
                                for line in f:
                                    line = line.strip()
                                    if not line or line.startswith("#"):
                                        continue
                                    if '=' in line:
                                        key, value = line.split('=', 1)
                                        local_env_vars[key.strip()] = value.strip()
                        except Exception as e:
                            print(f"Error loading env file: {e}")
                            return f"Failed to load env file: {env_filename}"
                    else:
                        print(f"Env file not found: {env_path}")
                        return f"Env file not found: {env_filename}"
                    skip_next = True
                continue
            if token == "--rm":
                rm_flag = True
                continue
            if token == "--name":
                if i + 1 < len(parts) and not container_name:
                    container_name = sanitize_string(parts[i+1])  # Sanitize container name
                skip_next = True
                continue
            if token == "--network":   # NEW: skip the network flag and its value
                skip_next = True
                continue
            cleaned_parts.append(token)

        # Ensure container name is sanitized
        if container_name:
            container_name = sanitize_string(container_name)

        # Ensure action is still "run"
        if action != "run":
            # ...existing handling for non-run commands...
            return f"Command executed: {docker_command}"

        # Extract image and container command arguments
        # cleaned_parts[0] is "run"
        if len(cleaned_parts) < 2:
            print("No image specified in the run command")
            return "No image specified"
        image = cleaned_parts[1]
        container_cmd = cleaned_parts[2:] if len(cleaned_parts) > 2 else None

        # New logic to set container name for known images if not provided
        if not container_name:
            if image == "data-collector" and container_cmd:
                # Look for '--date'
                for i, token in enumerate(container_cmd):
                    if token == "--date" and i+1 < len(container_cmd):
                        date_value = container_cmd[i+1].replace('"','')
                        container_name = f"data-collector-{date_value}"
                        break
            elif image == "history-collector" and container_cmd:
                # Look for '--title'
                for i, token in enumerate(container_cmd):
                    if token == "--title" and i+1 < len(container_cmd):
                        title = container_cmd[i+1].replace('"','')
                        formatted_title = title.lower().replace(' ', '-')
                        container_name = f"history-collector-{formatted_title}"
                        break

        # Auto-generate container name if still not defined
        if not container_name:
            container_name = "container-" + str(uuid.uuid4())[:8]
        run_kwargs = {
            "image": image,
            "command": container_cmd,
            "detach": True,
            "environment": local_env_vars,
            "remove": rm_flag,
            "network": "wave_default"  # added network parameter
        }
        run_kwargs["name"] = sanitize_string(container_name)
        print(f"Using container name: {run_kwargs['name']}")

        container = client.containers.run(**run_kwargs)

        # Stream logs from the container
        logs = ""
        for log in container.logs(stream=True):
            logs += log.decode("utf-8")
        container.wait()  # Ensure container has finished
        print(f"Executed command; output:\n{logs}")
        return logs
    except Exception as e:
        print(f"Error executing docker command: {e}")
        return f"Error executing docker command: {e}"

def stream_docker_command(client, job_id, docker_command, chain_command=None, env_vars=None, container_name=None):
    """
    Stream logs from a Docker command execution.

    Args:
        client (docker.DockerClient): The Docker client instance.
        job_id (str): The ID of the job.
        docker_command (str): The Docker command to execute.
        chain_command (str, optional): A command to execute after the main command.
        env_vars (dict, optional): Environment variables for the container.
        container_name (str, optional): The name of the container.

    Yields:
        str: Logs or error messages from the executed command.
    """
    print(f"Streaming docker command: {docker_command}")
    try:
        parts = shlex.split(docker_command)  # use shlex.split for proper argument parsing
        # Remove leading "docker" token if provided
        if parts and parts[0].lower() == "docker":
            parts = parts[1:]
        if not parts:
            yield "Empty docker command"
            return
        action = parts[0]

        local_env_vars = env_vars
        rm_flag = False
        cleaned_parts = []
        skip_next = False
        for i, token in enumerate(parts):
            if skip_next:
                skip_next = False
                continue
            if token == "--env-file":
                if i + 1 < len(parts):
                    env_filename = parts[i+1]
                    env_path = os.path.join("/data", "env", env_filename)
                    if os.path.exists(env_path):
                        try:
                            local_env_vars = {}
                            with open(env_path) as f:
                                for line in f:
                                    line = line.strip()
                                    if not line or line.startswith("#"):
                                        continue
                                    if '=' in line:
                                        key, value = line.split('=', 1)
                                        local_env_vars[key.strip()] = value.strip()
                        except Exception as e:
                            yield f"Error loading env file: {e}"
                            return
                    else:
                        yield f"Env file not found: {env_filename}"
                        return
                    skip_next = True
                continue
            if token == "--rm":
                rm_flag = True
                continue
            if token == "--name":
                if i + 1 < len(parts) and not container_name:
                    container_name = sanitize_string(parts[i+1])  # Sanitize container name
                skip_next = True
                continue
            if token == "--network":   # NEW: skip the network token and its value
                skip_next = True
                continue
            cleaned_parts.append(token)

        # Ensure container name is sanitized
        if container_name:
            container_name = sanitize_string(container_name)

        if action != "run":
            yield f"Command executed: {docker_command}"
            return

        if len(cleaned_parts) < 2:
            yield "No image specified"
            return
        image = cleaned_parts[1]
        container_cmd = cleaned_parts[2:] if len(cleaned_parts) > 2 else None

        # New logic to set container name for known images if not provided
        if not container_name:
            if image == "data-collector" and container_cmd:
                for i, token in enumerate(container_cmd):
                    if token == "--date" and i+1 < len(container_cmd):
                        date_value = container_cmd[i+1].replace('"','')
                        container_name = f"data-collector-{date_value}"
                        break
            elif image == "history-collector" and container_cmd:
                for i, token in enumerate(container_cmd):
                    if token == "--title" and i+1 < len(container_cmd):
                        title = container_cmd[i+1].replace('"','')
                        formatted_title = title.lower().replace(' ', '-')
                        container_name = f"history-collector-{formatted_title}"
                        break

        if not container_name:
            container_name = "container-" + str(uuid.uuid4())[:8]
            yield f"Auto-generated container name: {container_name}\n"
        else:
            yield f"Using container name: {sanitize_string(container_name)}\n"

        run_kwargs = {
            "image": image,
            "command": container_cmd,
            "detach": True,
            "environment": local_env_vars,
            "remove": rm_flag,
            "network": "wave_default"
        }
        run_kwargs["name"] = sanitize_string(container_name)

        container = client.containers.run(**run_kwargs)

        for log in container.logs(stream=True):
            yield log.decode("utf-8")
        container.wait()
        yield "\nCommand completed."
    except Exception as e:
        yield f"Error executing docker command: {e}"

def monitor_docker_events(client, chained_containers):
    """
    Monitor Docker events and handle container lifecycle events.

    Args:
        client (docker.DockerClient): The Docker client instance.
        chained_containers (dict): A dictionary mapping container names to chained commands.
    """
    for event in client.events(decode=True):
        if event.get("Type") == "container" and event.get("Action") == "die":
            container_id = event.get("id")
            try:
                container = client.containers.get(container_id)
                container_name = container.name
                logs = container.logs(tail=10).decode('utf-8', errors='replace')
                print(f"Container '{container_name}' has stopped. Recent logs:\n{logs}")
                if container_name in chained_containers:
                    chain_info = chained_containers[container_name]
                    print(f"Starting chained command for container {container_name}: {chain_info.get('chain_command')}")
                    execute_docker_command(client, chain_info.get('job_id'), chain_info.get('chain_command'))
                    del chained_containers[container_name]
            except Exception as e:
                print(f"Error processing container event: {e}")
        elif event.get("Type") == "container" and event.get("Action") == "start":
            try:
                container = client.containers.get(event.get("id"))
                print(f"Container '{container.name}' started")
            except Exception as e:
                print(f"Error fetching container info: {e}")

