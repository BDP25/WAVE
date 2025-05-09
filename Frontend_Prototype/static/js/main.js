import { fetchClusters, fetchArticleHistory } from "./api.js";
import { createDateSliderWithPicker } from "./slider.js";

let clustersData = [];
let flatpickrInstance = null;

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
            const link = createArticleLink(article);
            item.appendChild(link);
            list.appendChild(item);
        });

        clusterDiv.appendChild(list);
        container.appendChild(clusterDiv);
    });
}

function createArticleLink(article) {
    const link = document.createElement("a");
    link.innerText = article;
    link.href = "#";
    link.addEventListener("click", e => {
        e.preventDefault();
        fetchWikipediaContent(article);
    });
    return link;
}

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
                summaryPlaceholder.innerText = "No article data available.";
            } else {
                summaryPlaceholder.remove(); // Remove loading placeholder
                displayArticleHistory(data, articleContainer, timestampsSection);
            }
        })
        .catch(err => {
            console.error("Error fetching timestamps:", err);
            timestampsSection.innerHTML = "<p>Error loading timestamps.</p>";
            summaryPlaceholder.innerText = "Error loading article data.";
        });
}

function displayArticleHistory(data, articleContainer, timestampsSection) {
    const articleId = data.article_id;

    const articleIdElement = document.createElement("p");
    articleIdElement.innerText = `Article ID: ${articleId}`;
    articleContainer.appendChild(articleIdElement);

    const timestamps = data.history.map(entry => ({
        revid: entry.revid,
        timestamp: entry.timestamp
    }));

    createDateSliderWithPicker(timestampsSection, timestamps, articleId);
}