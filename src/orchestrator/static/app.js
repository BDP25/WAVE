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
        // Sort containers: items with names starting with 'wave-' come first
        const sorted = data.containers.sort((a, b) => {
          const aWave = a.name.startsWith('wave-') ? 0 : 1;
          const bWave = b.name.startsWith('wave-') ? 0 : 1;
          return aWave !== bWave ? aWave - bWave : a.name.localeCompare(b.name);
        });
        sorted.forEach(container => {
          const li = document.createElement('li');
          li.classList.add('container-item');
          if (container.name.startsWith('wave-')) {
            li.classList.add('wave-container');
          }
          li.innerHTML = `
            <div class="container-info">
              <span class="container-name">${container.name}</span>
              <span class="container-uptime">Uptime: ${container.uptime}</span>
            </div>
            <div class="status-indicator"></div>
          `;
          list.appendChild(li);
        });
      })
      .catch(err => console.error('Error fetching containers:', err));
  }

  // Function to fetch and display scheduled jobs
  function fetchJobs() {
    fetch(`${basePath}/api/jobs`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        const jobsList = document.getElementById('scheduledJobs');
        jobsList.innerHTML = '';

        if (!data.jobs || data.jobs.length === 0) {
          jobsList.innerHTML = '<p>No scheduled jobs</p>';
          return;
        }

        data.jobs.forEach(job => {
          const jobEl = document.createElement('div');
          jobEl.className = 'job-item';

          const jobInfo = document.createElement('div');
          jobInfo.className = 'job-info';

          const description = document.createElement('h3');
          description.textContent = job.job_name || 'Unnamed Job';

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
      .catch(err => {
        console.error('Error fetching jobs:', err);
        const jobsList = document.getElementById('scheduledJobs');
        jobsList.innerHTML = '<p>Error loading scheduled jobs</p>';
      });
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
  const jobName = document.getElementById('job_name').value;
  const command = document.getElementById('job_command').value;
  const delay = parseInt(document.getElementById('job_delay').value, 10);
  const chain = document.getElementById('job_chain').value || null;
  const cron = document.getElementById('job_cron').value || null;
  const recurring = document.getElementById('job_recurring').checked; // NEW: Get recurring flag
  fetch(`${basePath}/api/schedule`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      docker_command: command,
      delay: delay,
      chain_command: chain,
      cron: cron,
      job_name: jobName,
      recurring: recurring // NEW: Send recurring flag
    })
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

  // Function to fetch and update queue status
  function updateQueueStatus() {
    fetch(`${basePath}/api/queue-status`)
      .then(response => response.json())
      .then(data => {
        // Update Date Collector section
        document.getElementById('dateQueueStats').textContent = data.date.stats;
        const dateJobsList = document.getElementById('dateJobsList');
        dateJobsList.innerHTML = '';
        const dateRunning = data.date.running_jobs;
        const dateUpcoming = data.date.upcoming_jobs;
        const dateCombined = dateRunning.concat(dateUpcoming);
        if (dateCombined.length === 0) {
          const li = document.createElement('li');
          li.textContent = 'Queue is currently empty';
          li.className = 'empty-queue';
          dateJobsList.appendChild(li);
        } else {
          dateCombined.forEach(job => {
            const isRunning = dateRunning.some(r => r.docker_command === job.docker_command);
            const li = document.createElement('li');
            li.textContent = job.container_name ? job.container_name : job.docker_command;
            li.className = isRunning ? 'running-job' : 'upcoming-job';
            dateJobsList.appendChild(li);
          });
        }

        // Update History Collector section
        document.getElementById('historyQueueStats').textContent = data.history.stats;
        const historyJobsList = document.getElementById('historyJobsList');
        historyJobsList.innerHTML = '';
        const historyRunning = data.history.running_jobs;
        const historyUpcoming = data.history.upcoming_jobs;
        const historyCombined = historyRunning.concat(historyUpcoming);
        if (historyCombined.length === 0) {
          const li = document.createElement('li');
          li.textContent = 'Queue is currently empty';
          li.className = 'empty-queue';
          historyJobsList.appendChild(li);
        } else {
          historyCombined.forEach(job => {
            const isRunning = historyRunning.some(r => r.docker_command === job.docker_command);
            const li = document.createElement('li');
            li.textContent = job.container_name ? job.container_name : job.docker_command;
            li.className = isRunning ? 'running-job' : 'upcoming-job';
            historyJobsList.appendChild(li);
          });
        }
      })
      .catch(err => console.error('Error fetching queue status:', err));
  }

  // Function to fetch and display completed jobs
  function fetchCompletedJobs() {
    const jobType = document.getElementById('jobTypeFilter').value;
    fetch(`${basePath}/api/completed-jobs?type=${jobType}`)
      .then(response => response.json())
      .then(data => {
        const jobsList = document.getElementById('completedJobsList');
        jobsList.innerHTML = '';

        if (!data.jobs || data.jobs.length === 0) {
          jobsList.innerHTML = '<p class="no-jobs">No completed jobs found</p>';
          document.getElementById('completedJobsCount').textContent = '(0)';
          return;
        }

        document.getElementById('completedJobsCount').textContent = `(${data.jobs.length})`;

        data.jobs.forEach(job => {
          const jobEl = document.createElement('div');
          jobEl.className = 'completed-job-item';

          const header = document.createElement('div');
          header.className = 'job-header';

          const jobType = job.type ? `<span class="job-type">${job.type}</span>` : '';
          const timestamp = new Date(job.completed_at).toLocaleString();

          header.innerHTML = `
            ${jobType}
            <span class="job-timestamp">${timestamp}</span>
          `;

          const command = document.createElement('div');
          command.className = 'job-command';
          command.innerHTML = `<strong>Command:</strong> <code>${job.docker_command}</code>`;

          const result = document.createElement('div');
          result.className = 'job-result';
          result.innerHTML = `<strong>Result:</strong><pre>${job.result || 'No output'}</pre>`;

          // Add collapsible behavior
          header.addEventListener('click', () => {
            jobEl.classList.toggle('expanded');
          });

          jobEl.appendChild(header);
          jobEl.appendChild(command);
          jobEl.appendChild(result);

          jobsList.appendChild(jobEl);
        });
      })
      .catch(err => console.error('Error fetching completed jobs:', err));
  }

  // Add event listeners for completed jobs panel
  const showCompletedBtn = document.getElementById('showCompletedJobs');
  if (showCompletedBtn) {
    showCompletedBtn.addEventListener('click', function() {
      document.getElementById('completedJobsPanel').style.display = 'block';
      showCompletedBtn.style.display = 'none'; // hide the show button when panel is open
      fetchCompletedJobs();
    });
  }

  const hideCompletedBtn = document.getElementById('hideCompletedJobs');
  if (hideCompletedBtn) {
    hideCompletedBtn.addEventListener('click', function() {
      document.getElementById('completedJobsPanel').style.display = 'none';
      if (showCompletedBtn) {
        showCompletedBtn.style.display = 'block'; // show the show button when panel is closed
      }
    });
  }

    // Add listener for date collection form submission
  const dateCollectionForm = document.getElementById('dateCollectionForm');
  if (dateCollectionForm) {
    dateCollectionForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const date = document.getElementById('collection_date').value;
      if (!date) {
        alert('Please select a date');
        return;
      }

      const statusDiv = document.getElementById('dateCollectionStatus');
      statusDiv.textContent = `Starting data collection for: ${date}...`;

      fetch(`${basePath}/api/collect-date`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ date: date })
      })
      .then(response => {
        if (!response.body) {
          throw new Error('ReadableStream not yet supported in this browser.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const outputEl = document.getElementById('commandOutput');
        outputEl.textContent = `Running date collection for: ${date}\n`;

        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              statusDiv.textContent = `Completed data collection for: ${date}`;
              fetchContainers(); // Refresh container list
              return;
            }
            const text = decoder.decode(value);
            outputEl.textContent += text;
            outputEl.scrollTop = outputEl.scrollHeight; // Auto-scroll
            read();
          });
        }
        read();
      })
      .catch(err => {
        console.error('Error collecting date data:', err);
        statusDiv.textContent = `Error: ${err.message}`;
      });
    });
  }

  const refreshCompletedBtn = document.getElementById('refreshCompletedJobs');
  if (refreshCompletedBtn) {
    refreshCompletedBtn.addEventListener('click', fetchCompletedJobs);
  }

  const jobTypeFilter = document.getElementById('jobTypeFilter');
  if (jobTypeFilter) {
    jobTypeFilter.addEventListener('change', fetchCompletedJobs);
  }

  // Initial calls to load data
  updateQueueStatus();

  // Set up periodic refreshes
  setInterval(updateQueueStatus, 5000);
  setInterval(fetchContainers, 1000);

  // Initial fetch calls to load containers, jobs, and presets
  fetchContainers();
  fetchJobs();
  fetchPresets();
});

