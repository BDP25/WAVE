// Global variable to store clusters data
let clustersData = [];

document.addEventListener("DOMContentLoaded", function() {

    document.getElementById("date-picker").dispatchEvent(new Event("change"));
});

document.getElementById("date-picker").addEventListener("change", function () {
    const selectedDate = this.value;
    console.log("Ausgewähltes Datum:", selectedDate); // Debug-Ausgabe

    // Fetch the cluster data for the selected date
    fetch(`/api/clusters?datum=${selectedDate}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error("Fehler:", data.error);
                return;
            }
            console.log("Clusterdaten erhalten:", data);

            // Store the data in the global clustersData variable
            clustersData = data.clusters;

            // Call loadClusterData to display the clusters
            loadClusterData();
        })
        .catch(err => console.error("Request-Fehler:", err));
});

// This function is responsible for loading cluster data into the container
function loadClusterData() {
    const clusterContainer = document.getElementById('cluster-container');
    clusterContainer.innerHTML = ""; // Clear the container

    // Check if clustersData is populated
    if (!clustersData || clustersData.length === 0) {
        clusterContainer.innerHTML = "Keine Cluster-Daten verfügbar.";
        return;
    }

    // Loop through clusters and display their Wikipedia articles
    clustersData.forEach((cluster, index) => {
        const clusterDiv = document.createElement('div');
        clusterDiv.classList.add('cluster');

        // Create a title with "Cluster X" instead of the cluster_id
        const clusterTitle = document.createElement('h3');
        clusterTitle.innerText = `Cluster ${index + 1}`; // Display "Cluster 1", "Cluster 2", etc.
        clusterDiv.appendChild(clusterTitle);

        // Create a list of Wikipedia articles
        const wikiList = document.createElement('ul');
        cluster.wikipedia_articles.forEach(article => {
            const listItem = document.createElement('li');
            const link = document.createElement('a');
            link.href = `https://en.wikipedia.org/wiki/${encodeURIComponent(article)}`;
            link.target = "_blank";
            link.innerText = article;
            listItem.appendChild(link);
            wikiList.appendChild(listItem);
        });

        clusterDiv.appendChild(wikiList);
        clusterContainer.appendChild(clusterDiv);
    });
}
