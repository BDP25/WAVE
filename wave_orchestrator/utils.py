import uuid
import docker
import datetime
import subprocess  # ...added subprocess import...
import os          # ...added os import...

def execute_docker_command(client, job_id, docker_command, chain_command=None, env_vars=None):
    print(f"Executing docker command: {docker_command}")
    try:
        parts = docker_command.split()
        if not parts:
            print("Empty docker command")
            return "Empty docker command"
        action = parts[0]
        
        # Process flags: --env-file and --rm
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
            cleaned_parts.append(token)
        
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

        print(f"Running container with image {image} and command {container_cmd}")
        container = client.containers.run(image, command=container_cmd, detach=True, environment=local_env_vars, remove=rm_flag)
        
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

def stream_docker_command(client, job_id, docker_command, chain_command=None, env_vars=None):
    print(f"Streaming docker command: {docker_command}")
    try:
        parts = docker_command.split()
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
            cleaned_parts.append(token)

        if action != "run":
            yield f"Command executed: {docker_command}"
            return

        if len(cleaned_parts) < 2:
            yield "No image specified"
            return
        image = cleaned_parts[1]
        container_cmd = cleaned_parts[2:] if len(cleaned_parts) > 2 else None

        yield f"Running container with image {image} and command {container_cmd}\n"
        container = client.containers.run(image, command=container_cmd, detach=True, environment=local_env_vars, remove=rm_flag)

        for log in container.logs(stream=True):
            yield log.decode("utf-8")
        container.wait()
        yield "\nCommand completed."
    except Exception as e:
        yield f"Error executing docker command: {e}"

def monitor_docker_events(client, chained_containers):
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

