document.addEventListener('DOMContentLoaded', () => {
  // Use the current URL path to determine the base URL
  const basePath = window.location.pathname.split('/').slice(0, -1).join('/') || '';

  // Function to fetch and display containers
  function fetchContainers() {
    fetch(`${basePath}/api/containers`)
      .then(response => response.json())
      .then(data => {
        const list = document.getElementById('containerList');
        list.innerHTML = '';
        data.containers.forEach(container => {
          const li = document.createElement('li');
          li.textContent = `${container.name} - Uptime: ${container.uptime}`;
          list.appendChild(li);
        });
      })
      .catch(err => console.error('Error fetching containers:', err));
  }

  // Function to fetch and display scheduled jobs
  function fetchJobs() {
    fetch(`${basePath}/api/jobs`)
      .then(response => response.json())
      .then(data => {
        const jobsList = document.getElementById('scheduledJobs');
        jobsList.innerHTML = '';

        if (data.jobs.length === 0) {
          jobsList.innerHTML = '<p>No scheduled jobs</p>';
          return;
        }

        data.jobs.forEach(job => {
          const jobEl = document.createElement('div');
          jobEl.className = 'job-item';

          const jobInfo = document.createElement('div');
          jobInfo.className = 'job-info';

          const description = document.createElement('h3');
          description.textContent = job.description || 'Unnamed Job';

          const command = document.createElement('p');
          command.textContent = `Command: ${job.docker_command}`;

          const nextRun = document.createElement('p');
          nextRun.textContent = `Next run: ${job.next_run || 'Not scheduled'}`;

          const chainInfo = document.createElement('p');
          if (job.chain_command) {
            chainInfo.textContent = `Chain: ${job.chain_command}`;
          } else {
            chainInfo.textContent = 'No chained command';
          }

          const deleteBtn = document.createElement('button');
          deleteBtn.className = 'delete-btn';
          deleteBtn.textContent = 'Delete';
          deleteBtn.onclick = () => deleteJob(job.id);

          jobInfo.appendChild(description);
          jobInfo.appendChild(command);
          jobInfo.appendChild(nextRun);
          jobInfo.appendChild(chainInfo);

          jobEl.appendChild(jobInfo);
          jobEl.appendChild(deleteBtn);

          jobsList.appendChild(jobEl);
        });
      })
      .catch(err => console.error('Error fetching jobs:', err));
  }

  // Function to delete a job
  function deleteJob(jobId) {
    if (confirm('Are you sure you want to delete this job?')) {
      fetch(`${basePath}/api/jobs/${jobId}`, {
        method: 'DELETE'
      })
      .then(response => response.json())
      .then(data => {
        alert(data.message);
        fetchJobs();
      })
      .catch(err => console.error('Error deleting job:', err));
    }
  }

  // Function to execute a Docker command immediately
  function executeImmediateCommand(command) {
    fetch(`${basePath}/api/execute`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ docker_command: command })
    })
    .then(response => {
      if (!response.body) {
        throw new Error('ReadableStream not yet supported in this browser.');
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const outputEl = document.getElementById('commandOutput');
      outputEl.textContent = "";
      function read() {
        reader.read().then(({ done, value }) => {
          if (done) return;
          outputEl.textContent += decoder.decode(value);
          read();
        });
      }
      read();
    })
    .catch(err => console.error('Error executing command:', err));
  }

  // New function to delete a command preset
  function deletePreset(presetId) {
    if (confirm('Are you sure you want to delete this preset?')) {
      fetch(`${basePath}/api/presets/${presetId}`, {
        method: 'DELETE'
      })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert(data.error);
        } else {
          alert(data.message);
          fetchPresets();
        }
      })
      .catch(err => console.error('Error deleting preset:', err));
    }
  }

  // Function to fetch and display command presets
  function fetchPresets() {
    fetch(`${basePath}/api/presets`)
      .then(response => response.json())
      .then(data => {
        const presetsList = document.getElementById('presetsList');
        presetsList.innerHTML = '';

        if (!data.presets || data.presets.length === 0) {
          presetsList.innerHTML = '<p>No command presets defined</p>';
          return;
        }

        data.presets.forEach(preset => {
          const presetEl = document.createElement('div');
          presetEl.className = 'preset-item';

          const presetInfo = document.createElement('div');
          presetInfo.className = 'preset-info';

          const name = document.createElement('h4');
          name.textContent = preset.name;

          const command = document.createElement('p');
          command.textContent = preset.command;

          presetInfo.appendChild(name);
          presetInfo.appendChild(command);

          // Execute button
          const executeBtn = document.createElement('button');
          executeBtn.className = 'execute-preset-btn';
          executeBtn.textContent = 'Execute';
          executeBtn.onclick = () => executePreset(preset.id);

          // Delete button
          const deleteBtn = document.createElement('button');
          deleteBtn.className = 'delete-preset-btn';
          deleteBtn.textContent = 'Delete';
          deleteBtn.onclick = () => deletePreset(preset.id);

          presetEl.appendChild(presetInfo);
          presetEl.appendChild(executeBtn);
          presetEl.appendChild(deleteBtn);

          presetsList.appendChild(presetEl);
        });
      })
      .catch(err => console.error('Error fetching presets:', err));
  }

  // Add listener for preset form submission
  const addPresetForm = document.getElementById('addPresetForm');
  addPresetForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const name = document.getElementById('preset_name').value;
    const command = document.getElementById('preset_command').value;
    fetch(`${basePath}/api/presets`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name: name, command: command })
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
      } else {
        alert(data.message);
        fetchPresets();
      }
    })
    .catch(err => console.error('Error adding preset:', err));
  });

  // Helper function to execute preset command
  function executePreset(presetId) {
    fetch(`${basePath}/api/presets/execute/${presetId}`, {
      method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
      } else {
        // Display response in the command output panel
        document.getElementById('commandOutput').textContent = data.result ? data.result : data.message;
        fetchContainers(); // Refresh containers list if needed
      }
    })
    .catch(err => console.error('Error executing preset:', err));
  }

  // Add listener for job scheduling form submission
  document.getElementById('jobForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const command = document.getElementById('job_command').value;
    const delay = parseInt(document.getElementById('job_delay').value, 10);
    const chain = document.getElementById('job_chain').value || null;
    fetch(`${basePath}/api/schedule`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ docker_command: command, delay: delay, chain_command: chain })
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
      } else {
        alert(data.message);
        fetchJobs();
      }
    })
    .catch(err => console.error('Error scheduling job:', err));
  });

  // Add listener for .env editor form submission
  const envForm = document.getElementById('envForm');
  if (envForm) {
    envForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const filename = document.getElementById('env_filename').value;
      const content = document.getElementById('env_content').value;
      fetch(`${basePath}/api/env`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ filename: filename, content: content })
      })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert(data.error);
        } else {
          alert(data.message);
        }
      })
      .catch(err => console.error('Error saving .env file:', err));
    });
  }

  // Add listener for .env editor "Load" button
  const loadEnvBtn = document.getElementById('loadEnv');
  if (loadEnvBtn) {
      loadEnvBtn.addEventListener('click', function() {
          const filename = document.getElementById('env_filename').value;
          fetch(`${basePath}/api/env?filename=${encodeURIComponent(filename)}`)
            .then(response => response.json())
            .then(data => {
               if (data.error) {
                   alert(data.error);
               } else {
                   document.getElementById('env_content').value = data.content;
               }
            })
            .catch(err => console.error('Error loading .env file:', err));
      });
  }

  // Add event listener for refresh button
  const refreshBtn = document.getElementById('refreshContainers');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', fetchContainers);
  }

  // Auto refresh Running Containers section every 5 seconds
  setInterval(fetchContainers, 5000);

  // Initial fetch calls to load containers, jobs, and presets
  fetchContainers();
  fetchJobs();
  fetchPresets();
});

