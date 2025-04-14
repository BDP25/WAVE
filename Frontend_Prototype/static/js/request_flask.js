let clustersData = [];

// Initialize the application on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("date-picker").dispatchEvent(new Event("change"));
});

// Handle date-picker change event
document.getElementById("date-picker").addEventListener("change", function () {
    const selectedDate = this.value;
    fetchClusters(selectedDate);
});

// Fetch clusters data from the API
function fetchClusters(selectedDate) {
    fetch(`/api/clusters?datum=${selectedDate}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error("Error loading clusters:", data.error);
                return;
            }
            clustersData = data.clusters;
            renderClusters();
        })
        .catch(err => console.error("Error fetching cluster data:", err));
}

// Render clusters in the UI
function renderClusters() {
    const container = document.getElementById("cluster-container");
    container.innerHTML = "";

    if (!clustersData || clustersData.length === 0) {
        container.innerHTML = "No cluster data available.";
        return;
    }

    clustersData.forEach((cluster, index) => {
        const clusterDiv = document.createElement("div");
        clusterDiv.classList.add("cluster");

        const title = document.createElement("h3");
        title.innerText = `Topic ${index + 1}`;
        clusterDiv.appendChild(title);

        const list = document.createElement("ul");
        cluster.wikipedia_articles.forEach(article => {
            const item = document.createElement("li");
            const link = createArticleLink(article);
            item.appendChild(link);
            list.appendChild(item);
        });

        clusterDiv.appendChild(list);
        container.appendChild(clusterDiv);
    });
}

// Create a clickable link for an article
function createArticleLink(article) {
    const link = document.createElement("a");
    link.href = "#";
    link.innerText = article;
    link.addEventListener("click", e => {
        e.preventDefault();
        fetchWikipediaContent(article);
    });
    return link;
}

// Fetch and display Wikipedia content for an article
function fetchWikipediaContent(article) {
    const articleContainer = document.getElementById("wiki-article");
    articleContainer.innerHTML = "";

    // Add article title
    const titleElement = document.createElement("h2");
    titleElement.style.fontWeight = "bold";
    titleElement.innerText = article;
    articleContainer.appendChild(titleElement);

    // Add loading placeholder
    const summaryPlaceholder = document.createElement("p");
    summaryPlaceholder.innerText = "Loading summary...";
    articleContainer.appendChild(summaryPlaceholder);

    // Add timestamps section
    const timestampsSection = document.createElement("div");
    timestampsSection.id = "timestamps-section";
    articleContainer.appendChild(timestampsSection);

    // Fetch article history
    const historyUrl = `/api/article_history?title=${encodeURIComponent(article)}`;
    fetch(historyUrl)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                timestampsSection.innerHTML = "<p>No timestamps found.</p>";
            } else {
                displayArticleHistory(data, articleContainer, timestampsSection);
            }
        })
        .catch(err => {
            console.error("Error fetching timestamps:", err);
            timestampsSection.innerHTML = "<p>Error loading timestamps.</p>";
        });
}

// Display article history and create a date slider
function displayArticleHistory(data, articleContainer, timestampsSection) {
    const articleIdElement = document.createElement("p");
    articleIdElement.innerText = `Article ID: ${data.article_id}`;
    articleContainer.appendChild(articleIdElement);

    const timestamps = data.history.map(entry => ({
        revid: entry.revid,
        timestamp: entry.timestamp
    }));

    createDateSliderWithPicker(timestampsSection, timestamps);
}


function createDateSliderWithPicker(container, history) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    const years = history.map(entry => new Date(entry.timestamp).getFullYear());
    const minYear = Math.min(...years);
    const maxYear = Math.max(...years);

    const sortedHistory = history.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const tenthToLastTimestamp = sortedHistory.length >= 10
        ? new Date(sortedHistory[sortedHistory.length - 10].timestamp)
        : new Date(sortedHistory[0].timestamp);

    const timelineAxis = createTimelineAxis(minYear, maxYear, history);
    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    if (slider.noUiSlider) slider.noUiSlider.destroy();

    // Adjust slider configuration for single-year ranges
    const sliderRange = minYear === maxYear
        ? { min: 0, max: 11 } // Months for a single year
        : { min: minYear, max: maxYear };

    const sliderStart = minYear === maxYear
        ? [new Date(tenthToLastTimestamp).getMonth(), 11] // Start with months
        : [tenthToLastTimestamp.getFullYear(), maxYear];

    noUiSlider.create(slider, {
        start: sliderStart,
        connect: true,
        range: sliderRange,
        step: 1,
        tooltips: [
            {
                to: value => {
                    if (minYear === maxYear) {
                        // For single year, format as YYYY-MM-DD
                        const month = Math.floor(value);
                        return `${minYear}-${String(month + 1).padStart(2, "0")}-01`;
                    }
                    return `${Math.round(value)}`; // For multi-year ranges, show the year
                },
                from: value => Number(value)
            },
            {
                to: value => {
                    if (minYear === maxYear) {
                        const month = Math.floor(value);
                        return `${minYear}-${String(month + 1).padStart(2, "0")}-01`;
                    }
                    return `${Math.round(value)}`;
                },
                from: value => Number(value)
            }
        ]
    });

    setupSliderTooltips(slider, tenthToLastTimestamp, maxYear, minYear === maxYear);
}

// Adjust timeline axis for single-year ranges
function createTimelineAxis(minYear, maxYear, history) {
    const timelineAxis = document.createElement("div");
    timelineAxis.className = "timeline-axis";

    const yearRange = maxYear - minYear;
    if (yearRange === 0) {
        // Single year: Generate labels for months
        for (let month = 0; month < 12; month += 2) {
            const label = document.createElement("span");
            label.className = "month-label";
            label.textContent = `${minYear}-${String(month + 1).padStart(2, "0")}`;
            timelineAxis.appendChild(label);
        }
    } else if (yearRange <= 2) {
        // Small range: Generate labels for every 3 months
        for (let year = minYear; year <= maxYear; year++) {
            for (let month = 0; month < 12; month += 3) {
                const label = document.createElement("span");
                label.className = "month-label";
                label.textContent = `${year}-${String(month + 1).padStart(2, "0")}`;
                timelineAxis.appendChild(label);
            }
        }
    } else if (yearRange <= 10) {
        // Medium range: Generate labels for every year
        for (let year = minYear; year <= maxYear; year++) {
            const yearLabel = document.createElement("span");
            yearLabel.className = "year-label";
            yearLabel.textContent = year;
            timelineAxis.appendChild(yearLabel);
        }
    } else {
        // Large range: Generate labels for every 5 years
        for (let year = minYear; year <= maxYear; year += 5) {
            const yearLabel = document.createElement("span");
            yearLabel.className = "year-label";
            yearLabel.textContent = year;
            timelineAxis.appendChild(yearLabel);
        }
    }

    return timelineAxis;
}

// Setup slider tooltips and handle date changes
function setupSliderTooltips(slider, tenthToLastTimestamp, maxYear) {
    const selectedDates = [tenthToLastTimestamp.toISOString().split("T")[0], null];

    setTimeout(() => {
        const tooltips = slider.querySelectorAll(".noUi-tooltip");

        tooltips.forEach((tooltip, index) => {
            tooltip.style.cursor = "pointer";

            tooltip.addEventListener("click", () => {
                const input = document.createElement("input");
                input.type = "date";
                input.className = "date-picker-input";
                input.value = index === 0 ? selectedDates[0] : maxYear;

                const rect = tooltip.getBoundingClientRect();
                input.style.left = `${rect.left}px`;
                input.style.top = `${rect.bottom + window.scrollY}px`;

                document.body.appendChild(input);

                input.addEventListener("change", () => {
                    const selectedDate = new Date(input.value).getFullYear();
                    selectedDates[index] = input.value;
                    tooltip.innerText = input.value;
                    slider.noUiSlider.setHandle(index, selectedDate);
                    input.remove();
                });

                input.addEventListener("input", () => {
                    const selectedDate = new Date(input.value).getFullYear();
                    slider.noUiSlider.setHandle(index, selectedDate);
                });

                const removeOnClickOutside = (e) => {
                    if (!input.contains(e.target)) {
                        input.remove();
                        document.removeEventListener("click", removeOnClickOutside);
                    }
                };

                setTimeout(() => {
                    document.addEventListener("click", removeOnClickOutside);
                }, 0);
            });
        });
    }, 200);
}