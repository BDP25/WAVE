import { fetchClusters, fetchArticleHistory } from "./api.js";
import { createDateSliderWithPicker } from "./slider.js";

let clustersData = [];

// Initialize the application on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("date-picker").dispatchEvent(new Event("change"));
});

// Handle date-picker change event
document.getElementById("date-picker").addEventListener("change", function () {
    const selectedDate = this.value;
    fetchClusters(selectedDate)
        .then(data => {
            if (data.error) {
                console.error("Error loading clusters:", data.error);
                return;
            }
            clustersData = data.clusters;
            renderClusters();
        })
        .catch(err => console.error("Error fetching cluster data:", err));
});

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

    fetchArticleHistory(article)
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

