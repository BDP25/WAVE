import uuid
import docker
import datetime

def execute_docker_command(client, job_id, docker_command, chain_command=None, env_vars=None):
    print(f"Executing docker command: {docker_command}")
    try:
        parts = docker_command.split()
        if not parts:
            print("Empty docker command")
            return
        action = parts[0]
        if action == "run":
            container_name = None
            try:
                name_index = parts.index("--name")
                if name_index < len(parts) - 1:
                    container_name = parts[name_index + 1]
            except ValueError:
                container_name = f"job-{job_id if job_id else 'immediate'}-{uuid.uuid4().hex[:8]}"
                parts.extend(["--name", container_name])
            if chain_command and container_name:
                # Assuming chained_containers is managed in app.py
                pass
            cmd = " ".join(parts[1:])
            # Pass env_vars to the container if provided
            container = client.containers.run(cmd, detach=True, environment=env_vars)
            print(f"Started container: {container.name}")
            return container.name
        elif action == "stop":
            if len(parts) > 1:
                container_name = parts[1]
                try:
                    container = client.containers.get(container_name)
                    container.stop()
                    print(f"Stopped container: {container_name}")
                    return f"Stopped container: {container_name}"
                except docker.errors.NotFound:
                    print(f"Container not found: {container_name}")
                    return f"Container not found: {container_name}"
        return f"Command executed: {docker_command}"
    except Exception as e:
        print(f"Error executing docker command: {e}")

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

