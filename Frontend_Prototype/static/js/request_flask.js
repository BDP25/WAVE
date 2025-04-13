let clustersData = [];

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("date-picker").dispatchEvent(new Event("change"));
});

document.getElementById("date-picker").addEventListener("change", function () {
    const selectedDate = this.value;

    fetch(`/api/clusters?datum=${selectedDate}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error("Fehler beim Laden der Cluster:", data.error);
                return;
            }

            clustersData = data.clusters;
            renderClusters();
        })
        .catch(err => console.error("Fehler beim Laden der Clusterdaten:", err));
});

function renderClusters() {
    const container = document.getElementById('cluster-container');
    container.innerHTML = "";

    if (!clustersData || clustersData.length === 0) {
        container.innerHTML = "Keine Cluster-Daten verfügbar.";
        return;
    }

    clustersData.forEach((cluster, index) => {
        const clusterDiv = document.createElement('div');
        clusterDiv.classList.add('cluster');

        const title = document.createElement('h3');
        title.innerText = `Thema ${index + 1}`;
        clusterDiv.appendChild(title);

        const list = document.createElement('ul');
        cluster.wikipedia_articles.forEach(article => {
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.href = "#";
            link.innerText = article;
            link.addEventListener("click", e => {
                e.preventDefault();
                fetchWikipediaContent(article);
            });
            item.appendChild(link);
            list.appendChild(item);
        });

        clusterDiv.appendChild(list);
        container.appendChild(clusterDiv);
    });
}







function fetchWikipediaContent(article) {
    const articleContainer = document.getElementById("wiki-article");
    articleContainer.innerHTML = "";

    // Titel
    const titleElement = document.createElement("h2");
    titleElement.style.fontWeight = "bold";
    titleElement.innerText = article;
    articleContainer.appendChild(titleElement);

    // Zusammenfassung
    const summaryPlaceholder = document.createElement("p");
    summaryPlaceholder.innerText = "Zusammenfassung wird geladen...";
    articleContainer.appendChild(summaryPlaceholder);

    // 🔁 Slider hinzufügen (ausgelagerte Funktion)
    createDateSliderWithPicker(articleContainer);

    // Wikipedia-API laden
    const url = `/api/wiki_content?title=${encodeURIComponent(article)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            summaryPlaceholder.innerText = data.summary || "Keine Zusammenfassung gefunden.";
        })
        .catch(err => {
            summaryPlaceholder.innerText = "Fehler beim Laden der Zusammenfassung.";
        });
}




function createDateSliderWithPicker(container) {
    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    // Slider erstellen
    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    // Zeitstrahl-Achse erstellen
    const timelineAxis = document.createElement("div");
    timelineAxis.className = "timeline-axis";

    // Jahreszahlen für die Achse generieren (von 2000 bis 2025 in 5er-Schritten)
    for (let year = 2000; year <= 2025; year += 5) {
        const yearLabel = document.createElement("span");
        yearLabel.className = "year-label";
        yearLabel.textContent = year;
        timelineAxis.appendChild(yearLabel);
    }

    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    // Slider konfigurieren
    noUiSlider.create(slider, {
        start: [2005, 2020],
        connect: true,
        range: {
            min: 2000,
            max: 2025
        },
        step: 1,
        tooltips: [
            { to: value => `${Math.round(value)}`, from: value => Number(value) },
            { to: value => `${Math.round(value)}`, from: value => Number(value) }
        ]
    });

    const selectedDates = [null, null];

    setTimeout(() => {
        const tooltips = slider.querySelectorAll('.noUi-tooltip');

        tooltips.forEach((tooltip, index) => {
            tooltip.style.cursor = "pointer";

            tooltip.addEventListener("click", () => {
                const year = tooltip.innerText;
                const input = document.createElement("input");
                input.type = "date";
                input.className = "date-picker-input";
                input.value = `${year}-06-30`;

                const rect = tooltip.getBoundingClientRect();
                input.style.left = `${rect.left}px`;
                input.style.top = `${rect.bottom + window.scrollY}px`;

                document.body.appendChild(input);

                input.addEventListener("change", () => {
                    selectedDates[index] = input.value;
                    tooltip.innerText = input.value;
                    input.remove();
                    console.log("📅 Gewähltes Datum", index === 0 ? "Start" : "Ende", "→", input.value);
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