import { fetchClusters, fetchArticleHistory, fetchClusterSummary } from "./api.js";
import { createDateSliderWithPicker } from "./slider.js";

let clustersData = [];
let flatpickrInstance = null;
let selectedClusterIndex = null;
let currentSelectedDate = null;
let cachedClusterSummary = null;
let lastDisplayedClusterIndex = null;  // Add this missing variable
let lastDisplayedClusterDate = null;   // Add this missing variable


// Initialize the application on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
    initializeFlatpickr();
});

function initializeFlatpickr() {
    const datePickerElement = document.getElementById("date-picker");
    const minDate = datePickerElement.dataset.minDate;
    const maxDate = datePickerElement.dataset.maxDate;

    // Create array of available dates between min and max
    const availableDates = [];
    const minDateObj = new Date(minDate);
    const maxDateObj = new Date(maxDate);

    const currentDate = new Date(minDateObj);
    while (currentDate <= maxDateObj) {
        availableDates.push(currentDate.toISOString().split('T')[0]);
        currentDate.setDate(currentDate.getDate() + 1);
    }

    // Get the start and end years for the dropdown
    const startYear = minDateObj.getFullYear();
    const endYear = maxDateObj.getFullYear();

    flatpickrInstance = flatpickr(datePickerElement, {
        dateFormat: "Y-m-d",
        minDate: minDate,
        maxDate: maxDate,
        defaultDate: maxDate,
        monthSelectorType: "dropdown",
        enable: availableDates,
        showMonths: 1,
        locale: {
            firstDayOfWeek: 1 // Start week on Monday (0 is Sunday)
        },
        onChange: function(selectedDates, dateStr) {
            loadClusterData(dateStr);
            currentSelectedDate = dateStr;  // Update the current selected date
        },
        onOpen: function(selectedDates, dateStr, instance) {
            // Apply custom ID to the calendar element for CSS scoping
            instance.calendarContainer.id = "date-picker-calendar";

            // Apply consistent styling each time calendar opens
            setTimeout(() => {
                applyCalendarFormatting(instance, minDateObj, maxDateObj, availableDates, startYear, endYear);
            }, 10);
        },
        onReady: function(selectedDates, dateStr, instance) {
            // Apply custom ID to the calendar element for CSS scoping
            instance.calendarContainer.id = "date-picker-calendar";
            instance.calendarContainer.classList.add("small-flatpickr");

            // Initial calendar formatting
            applyCalendarFormatting(instance, minDateObj, maxDateObj, availableDates, startYear, endYear);
        },
        onDayCreate: function(dObj, dStr, fp, dayElem) {
            if (!dayElem.dateObj) return;

            const dateStr = dayElem.dateObj.toISOString().split('T')[0];

            if (dayElem.dateObj >= minDateObj &&
                dayElem.dateObj <= maxDateObj &&
                availableDates.includes(dateStr)) {
                dayElem.classList.remove("flatpickr-disabled");
                dayElem.removeAttribute("disabled");
            }
        },
        onMonthChange: function(selectedDates, dateStr, instance) {
            setTimeout(() => {
                applyCalendarFormatting(instance, minDateObj, maxDateObj, availableDates, startYear, endYear);
            }, 10);
        }
    });

    // Initial data load
    currentSelectedDate = maxDate;  // Initialize currentSelectedDate
    loadClusterData(maxDate);
}

function applyCalendarFormatting(instance, minDateObj, maxDateObj, availableDates, startYear, endYear) {
    // Customize weekday headers to use abbreviated names
    const weekdays = instance.calendarContainer.querySelectorAll('.flatpickr-weekday');
    weekdays.forEach(weekday => {
        weekday.textContent = weekday.textContent.substring(0, 2); // Two letter abbreviation
    });

    // Set up year dropdown if it doesn't exist
    if (!instance.calendarContainer.querySelector('.flatpickr-yearDropdown')) {
        convertYearNavigationToDropdown(instance, startYear, endYear);
    }

    // Make sure all dates in range are enabled
    enableValidDates(instance, minDateObj, maxDateObj, availableDates);
}

function enableValidDates(instance, minDateObj, maxDateObj, availableDates) {
    if (!instance.days || !instance.days.childNodes) return;

    Array.from(instance.days.childNodes).forEach(day => {
        if (!day.dateObj) return;

        const dateStr = day.dateObj.toISOString().split('T')[0];

        // Remove any special styling classes except for selected
        day.classList.remove("valid-entry-day", "minDate");
        day.removeAttribute("data-is-min-date");

        // Only enable dates in range
        if (day.dateObj >= minDateObj &&
            day.dateObj <= maxDateObj &&
            availableDates.includes(dateStr)) {
            day.classList.remove("flatpickr-disabled");
            day.removeAttribute("disabled");
        }
    });
}

function convertYearNavigationToDropdown(instance, startYear, endYear) {
    setTimeout(() => {
        const calendarContainer = instance.calendarContainer;
        const currentYearElement = calendarContainer.querySelector('.cur-year');
        const monthDropdown = calendarContainer.querySelector('.flatpickr-monthDropdown-months');

        if (!currentYearElement || !monthDropdown) return;

        // Remove arrow controls
        const yearParent = currentYearElement.parentNode;
        const yearArrows = yearParent.querySelectorAll('.arrowUp, .arrowDown');
        yearArrows.forEach(arrow => arrow.remove());

        const currentYear = parseInt(currentYearElement.textContent);

        // Check if year dropdown already exists
        if (calendarContainer.querySelector('.flatpickr-yearDropdown')) return;

        const yearSelect = document.createElement('select');
        yearSelect.className = 'flatpickr-yearDropdown';

        monthDropdown.classList.add('flatpickr-monthDropdown-enhanced');

        for (let year = startYear; year <= endYear; year++) {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            if (year === currentYear) {
                option.selected = true;
            }
            yearSelect.appendChild(option);
        }

        yearSelect.addEventListener('change', (e) => {
            const newYear = parseInt(e.target.value);
            const currentMonth = instance.currentMonth;
            instance.changeYear(newYear);

            // Maintain the month when changing year
            if (instance.currentMonth !== currentMonth) {
                instance.changeMonth(currentMonth, false);
            }
        });

        yearParent.replaceChild(yearSelect, currentYearElement);
    }, 0);
}

function loadClusterData(selectedDate) {
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
}



function renderClusters() {
    const container = document.getElementById("cluster-container");
    container.innerHTML = "";

    if (!clustersData || clustersData.length === 0) {
        container.innerHTML = "<div class='no-clusters'>No cluster data available.</div>";
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
            const link = document.createElement("a");
            link.innerText = article;
            link.href = "#";
            link.addEventListener("click", e => {
                e.preventDefault();
                selectedClusterIndex = index; // Cluster speichern
                fetchWikipediaContent(article);

                // Add summary section to article container
                const articleContainer = document.getElementById("wiki-article");
                if (!document.getElementById("summary-section")) {
                    const summarySection = document.createElement("div");
                    summarySection.id = "summary-section";
                    summarySection.classList.add("article-summary");
                    summarySection.innerHTML = "<p>Loading cluster summary...</p>";
                    articleContainer.insertBefore(summarySection, articleContainer.firstChild.nextSibling);
                }

                // Get the summary for this cluster
                displayClusterSummary();

                // TODO testin
                testSelectArticleByCluster(currentSelectedDate, selectedClusterIndex)
            });
            item.appendChild(link);
            list.appendChild(item);
        });

        clusterDiv.appendChild(list);
        container.appendChild(clusterDiv);
    });
}


function displayClusterSummary() {
    if (selectedClusterIndex === null || currentSelectedDate === null) {
        return;
    }

    const summarySection = document.getElementById("summary-section");
    if (!summarySection) return;

    // Check if we're requesting the same cluster and date as before
    if (selectedClusterIndex === lastDisplayedClusterIndex &&
        currentSelectedDate === lastDisplayedClusterDate &&
        cachedClusterSummary !== null) {
        console.log("Using cached cluster summary");
        summarySection.innerHTML = cachedClusterSummary;
        return;
    }

    summarySection.innerHTML = "<p>Loading cluster summary...</p>";

    // Fix the parameter order here
    fetchClusterSummary(selectedClusterIndex, currentSelectedDate)
        .then(data => {
            if (data.error) {
                summarySection.innerHTML = `<p class="error-message">Error loading summary: ${data.error}</p>`;
                console.error("Error loading summary:", data.error);
            } else {
                const summaryHTML = `
                    <h3>Cluster Summary</h3>
                    <div class="summary-content">${data.summary}</div>
                `;
                summarySection.innerHTML = summaryHTML;

                // Cache the summary and record which cluster/date it's for
                lastDisplayedClusterIndex = selectedClusterIndex;
                lastDisplayedClusterDate = currentSelectedDate;
                cachedClusterSummary = summaryHTML;
            }
        })
        .catch(err => {
            console.error("Error fetching cluster summary:", err);
            summarySection.innerHTML = `<p class="error-message">Failed to load summary: ${err.message}</p>`;
        });
}



function fetchWikipediaContent(article) {
    const articleContainer = document.getElementById("wiki-article");
    articleContainer.innerHTML = "";

    // Add article title
    const titleElement = document.createElement("l2");
    titleElement.style.fontWeight = "bold";
    titleElement.innerText = article;
    articleContainer.appendChild(titleElement);

    // Add loading placeholder
    const summaryPlaceholder = document.createElement("p");
    summaryPlaceholder.innerText = "Loading article data...";
    summaryPlaceholder.id = "loading-placeholder";
    articleContainer.appendChild(summaryPlaceholder);

    // Add timestamps section
    const timestampsSection = document.createElement("div");
    timestampsSection.id = "timestamps-section";
    timestampsSection.innerHTML = "<p>Loading revision history...</p>";
    articleContainer.appendChild(timestampsSection);

    console.log(`Fetching article history for: ${article}`);

    fetchArticleHistory(article)
        .then(data => {
            console.log("Article history response:", data);
            document.getElementById("loading-placeholder").remove();

            if (data.error) {
                console.error("Error in article history:", data.error);
                displayArticleHistory(data, articleContainer, timestampsSection);
            } else {
                displayArticleHistory(data, articleContainer, timestampsSection);

                // After displaying article history, add summary section
                if (!document.getElementById("summary-section") && selectedClusterIndex !== null) {
                    const summarySection = document.createElement("div");
                    summarySection.id = "summary-section";
                    summarySection.classList.add("article-summary");

                    // Insert after title but before timestamps
                    articleContainer.insertBefore(summarySection, titleElement.nextSibling);

                    // Request cluster summary
                    displayClusterSummary();
                }
            }
        })
        .catch(err => {
            console.error("Error fetching article history:", err);
            summaryPlaceholder.remove();

            const errorElement = document.createElement("div");
            errorElement.classList.add("error-message");
            errorElement.innerHTML = `
                <p><strong>Error:</strong> Failed to fetch article history</p>
                <p>Technical details: ${err.message}</p>
            `;
            timestampsSection.innerHTML = "";
            timestampsSection.appendChild(errorElement);
        });
}


function displayArticleHistory(data, articleContainer, timestampsSection) {
    // Check if there's an error and handle it more gracefully
    if (data.error) {
        console.error("Error from API:", data.error);
        const errorElement = document.createElement("div");
        errorElement.classList.add("error-message");
        errorElement.innerHTML = `
            <p><strong>Error:</strong> ${data.error}</p>
            <p>Please try another article or contact the administrator if this issue persists.</p>
        `;
        timestampsSection.innerHTML = "";
        timestampsSection.appendChild(errorElement);
        return;
    }

    const articleId = data.article_id;

    const articleIdElement = document.createElement("p");


    // Check if history exists and has entries
    if (!data.history || data.history.length === 0) {
        timestampsSection.innerHTML = "<p>No revision history available for this article.</p>";
        return;
    }

    const timestamps = data.history.map(entry => ({
        revid: entry.revid,
        timestamp: entry.timestamp
    }));

    createDateSliderWithPicker(timestampsSection, timestamps, articleId);
}




// TODO Testing
// TESTING FUNCTION: Selectbox for articles by date and cluster index
function testSelectArticleByCluster(date, clusterIndex) {
    fetch(`/api/test-articles?date=${encodeURIComponent(date)}&cluster=${clusterIndex}`)
        .then(response => response.json())
        .then(data => {
            if (data.error || !data.articles) {
                alert("No articles found or error: " + (data.error || "Unknown error"));
                return;
            }

            // Remove old select/content if present
            document.getElementById("test-article-select")?.remove();
            document.getElementById("test-article-content")?.remove();

            // Find a visible container (e.g., wiki-article)
            const container = document.getElementById("wiki-article") || document.body;

            // Create select box
            let select = document.createElement("select");
            select.id = "test-article-select";
            // Make text larger and more readable
            select.style.fontSize = "1.2em";
            select.style.padding = "0.5em";
            select.style.minWidth = "350px";

            data.articles.forEach(article => {
                let option = document.createElement("option");
                option.value = article.article_id;
                option.textContent = `${article.article_id} | ${article.head}`;
                select.appendChild(option);
            });

            // Display area for article head
            let contentDiv = document.createElement("div");
            contentDiv.id = "test-article-content";
            contentDiv.style.marginTop = "1em";

            // On select, display article head
            select.addEventListener("change", function() {
                const selected = data.articles.find(a => a.article_id == this.value);
                contentDiv.textContent = selected ? selected.head : "No head";
            });

            // Insert select and contentDiv at the top of the container
            container.insertBefore(contentDiv, container.firstChild);
            container.insertBefore(select, container.firstChild);

            // Show first article by default
            if (data.articles.length > 0) {
                select.value = data.articles[0].article_id;
                contentDiv.textContent = data.articles[0].head;
            }
        })
        .catch(err => alert("Error fetching articles: " + err));
}