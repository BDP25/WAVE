

// Fetch clusters data from the API
export function fetchClusters(selectedDate) {
    return fetch(`/api/clusters?datum=${selectedDate}`).then(res => res.json());
}

// Fetch article history from the API
export function fetchArticleHistory(article) {
    const historyUrl = `/api/article_history?title=${encodeURIComponent(article)}`;
    return fetch(historyUrl).then(res => res.json());
}

// Fetch visualization data from the API
export function fetchVisualization(articleId, startRevid, endRevid, signal) {
    const visualizeUrl = `/api/visualize?article_id=${articleId}&start_revid=${startRevid}&end_revid=${endRevid}`;
    return fetch(visualizeUrl, { signal }).then(res => res.json());
}

// Fetch cluster summary from the API
export function fetchClusterSummary(clusterId, selectedDate) {
    const summaryUrl = `/api/cluster_summary?cluster_id=${clusterId}&date=${encodeURIComponent(selectedDate)}`;
    return fetch(summaryUrl).then(res => res.json());
}

