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
    document.getElementById("intro-section").style.display = "block";

    // Add click event listener to the logo in the sidebar
    // Add click event listener to the logo in the sidebar
    const logoElement = document.querySelector('.sidebar .logo');
    if (logoElement) {
        logoElement.addEventListener('click', (e) => {
            // Reload the page instead of trying to show intro section
            window.location.reload();
        });
    }

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
                    <h3>Cluster-Zusammenfasung</h3>
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
    // Hide intro if present
    const introSection = document.getElementById("intro-section");
    if (introSection) introSection.style.display = "none";
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

    // Add event listener for when visualization content is loaded
    document.addEventListener('visualizationLoaded', setupUserHoverPopups);
}

// Fix the user hover popups function to correctly identify users
function setupUserHoverPopups() {
    console.log("Setting up user hover popups");

    // Remove any existing popup to avoid duplicates
    const existingPopup = document.getElementById('user-info-popup');
    if (existingPopup) {
        existingPopup.remove();
    }

    // Create popup element
    const popup = document.createElement('div');
    popup.id = 'user-info-popup';
    popup.className = 'user-info-popup';
    popup.style.display = 'none';
    document.body.appendChild(popup);

    // Find elements with user-add or user-del attributes in the output container
    const outputContainer = document.querySelector('.output-container') || document.getElementById('wiki-article');
    if (!outputContainer) {
        console.log("No output container found");
        return;
    }

    // Select all spans with user attributes - use broader selectors to match all variations
    const userElements = outputContainer.querySelectorAll('[user-add], [user-del], [data-user-add], [data-user-del]');

    console.log(`Found ${userElements.length} elements with user attribution`);

    userElements.forEach(element => {
        // Get user information from the element - check all possible attribute combinations
        let username = null;

        // Check data attributes first
        if (element.hasAttribute('data-user-add')) {
            username = element.getAttribute('data-user-add');
        } else if (element.hasAttribute('data-user-del')) {
            username = element.getAttribute('data-user-del');
        }
        // Then check direct user-add/user-del attributes
        else if (element.hasAttribute('user-add')) {
            username = element.getAttribute('user-add');
            // If value is "user", try to find the actual username in content
            if (username === "user") {
                username = element.textContent.trim();
            }
        } else if (element.hasAttribute('user-del')) {
            username = element.getAttribute('user-del');
            // If value is "user", try to find the actual username in content
            if (username === "user") {
                username = element.textContent.trim();
            }
        }

        if (!username) {
            console.log("No username found for element:", element.outerHTML);
            return;
        }

        console.log(`Found user element with username: ${username}`);

        // Cache for IP data to avoid repeated requests
        let ipDataCache = null;

        // Add hover event listeners
        element.addEventListener('mouseenter', async (e) => {
            // Get viewport dimensions
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight;

            // Make the popup visible but with opacity 0 to measure its size
            popup.style.opacity = '0';
            popup.style.display = 'block';

            // Set initial content based on user type to get approximate dimensions
            if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(username)) {
                popup.innerHTML = `<strong>Anonymous Editor (IPv4)</strong><br>IP: ${username}`;
            } else if (/^[0-9a-fA-F:]+$/.test(username) && username.includes(':')) {
                popup.innerHTML = `<strong>Anonymous Editor (IPv6)</strong><br>IP: ${username}`;
            } else {
                popup.innerHTML = `<strong>Wikipedia Editor</strong><br>Username: ${username}`;
            }

            // Get popup dimensions after setting initial content
            const popupWidth = popup.offsetWidth;
            const popupHeight = popup.offsetHeight;

            // Calculate position that keeps popup within viewport
            let leftPos = e.pageX + 10;
            let topPos = e.pageY + 10;

            // Check right edge of screen
            if (leftPos + popupWidth > viewportWidth - 20) {
                leftPos = e.pageX - popupWidth - 10; // Position to the left of cursor
            }

            // Check bottom edge of screen
            if (topPos + popupHeight > viewportHeight - 20) {
                topPos = e.pageY - popupHeight - 10; // Position above cursor
            }

            // Ensure popup doesn't go off left or top edge
            leftPos = Math.max(10, leftPos);
            topPos = Math.max(10, topPos);

            // Set the calculated position
            popup.style.left = `${leftPos}px`;
            popup.style.top = `${topPos}px`;

            // Now make the popup visible again
            popup.style.opacity = '1';

            // Determine user type and set content accordingly
            // Check if IPv4 address (simple regex pattern)
            if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(username)) {
                popup.innerHTML = `
                    <strong>Anonymous Editor (IPv4)</strong><br>
                    IP: ${username}<br>
                    <div class="loading-spinner">Loading additional information...</div>
                `;

                // Fetch additional IP information if not already cached
                if (!ipDataCache) {
                    try {
                        const response = await fetch(`/api/ip_info?ip=${encodeURIComponent(username)}`);
                        ipDataCache = await response.json();
                    } catch (error) {
                        console.error("Error fetching IP info:", error);
                        ipDataCache = { error: "Failed to load IP information" };
                    }
                }

                // Update the popup with the detailed information
                displayIPDetails(username, ipDataCache, popup, "IPv4");

                // Recheck position after content update
                recheckPopupPosition(popup, leftPos, topPos, viewportWidth, viewportHeight);
            }
            // Check if IPv6 address - look for hex digits and colons
            else if (/^[0-9a-fA-F:]+$/.test(username) && username.includes(':')) {
                popup.innerHTML = `
                    <strong>Anonymous Editor (IPv6)</strong><br>
                    IP: ${username}<br>
                    <div class="loading-spinner">Loading additional information...</div>
                `;

                // Fetch additional IP information if not already cached
                if (!ipDataCache) {
                    try {
                        const response = await fetch(`/api/ip_info?ip=${encodeURIComponent(username)}`);
                        ipDataCache = await response.json();
                    } catch (error) {
                        console.error("Error fetching IP info:", error);
                        ipDataCache = { error: "Failed to load IP information" };
                    }
                }

                // Update the popup with the detailed information
                displayIPDetails(username, ipDataCache, popup, "IPv6");

                // Recheck position after content update
                recheckPopupPosition(popup, leftPos, topPos, viewportWidth, viewportHeight);
            }
            // Regular username
            else {
                const popupContent = `
                    <strong>Wikipedia Editor</strong><br>
                    Username: ${username}
                `;
                popup.innerHTML = popupContent;

                // Recheck position after content update
                recheckPopupPosition(popup, leftPos, topPos, viewportWidth, viewportHeight);
            }
        });

        element.addEventListener('mouseleave', () => {
            popup.style.display = 'none';
        });
    });
}

// Helper function to recheck and adjust popup position after content is updated
function recheckPopupPosition(popup, leftPos, topPos, viewportWidth, viewportHeight) {
    // Get updated popup dimensions after content has changed
    const updatedPopupWidth = popup.offsetWidth;
    const updatedPopupHeight = popup.offsetHeight;

    // Check right edge of screen again
    if (leftPos + updatedPopupWidth > viewportWidth - 20) {
        leftPos = Math.max(10, viewportWidth - updatedPopupWidth - 20);
        popup.style.left = `${leftPos}px`;
    }

    // Check bottom edge of screen again
    if (topPos + updatedPopupHeight > viewportHeight - 20) {
        topPos = Math.max(10, viewportHeight - updatedPopupHeight - 20);
        popup.style.top = `${topPos}px`;
    }
}

// Helper function to display IP details in the popup
function displayIPDetails(ip, ipData, popup, ipType) {
    // Check if there was an error fetching the data
    if (ipData.error) {
        popup.innerHTML = `
            <strong>Anonymous Editor (${ipType})</strong><br>
            IP: ${ip}<br>
            <div class="error-message">${ipData.error}</div>
        `;
        return;
    }

    // Extract relevant information from the whois data
    const results = ipData.whois_data?.results;
    let content = `
        <strong>Anonymous Editor (${ipType})</strong><br>
        <div class="ip-info-section">
            <div class="ip-address">${ip}</div>
    `;

    if (results) {
        // Add network information
        content += `
            <div class="ip-details">
                <table class="ip-info-table">
                    <tr>
                        <td>Network:</td>
                        <td>${results.prefix || 'Unknown'}</td>
                    </tr>
        `;

        // Add ASN information if available
        if (results.asns && results.asns.length > 0) {
            content += `
                <tr>
                    <td>ASN:</td>
                    <td>${results.asns.join(', ')}</td>
                </tr>
            `;
        }

        // Add organization information if available
        if (results.as2org && results.as2org.length > 0) {
            const org = results.as2org[0].org;
            if (org) {
                content += `
                    <tr>
                        <td>Organization:</td>
                        <td>${org.ASORG || 'Unknown'}</td>
                    </tr>
                    <tr>
                        <td>Country:</td>
                        <td>${org.CC || 'Unknown'}</td>
                    </tr>
                `;
            }

            // Add AS Name if available
            if (results.as2org[0].ASNAME) {
                content += `
                    <tr>
                        <td>AS Name:</td>
                        <td>${results.as2org[0].ASNAME}</td>
                    </tr>
                `;
            }
        }

        content += `
                </table>
            </div>
        `;
    } else {
        content += `<div class="no-data-message">No additional network information available</div>`;
    }

    content += `</div>`;
    popup.innerHTML = content;
}

// Create a custom event that will be triggered when visualization is loaded
function createVisualizationLoadedEvent() {
    // Create and dispatch the event
    const event = new CustomEvent('visualizationLoaded');
    document.dispatchEvent(event);
}

// Extend the existing API module to expose the event creation function
window.createVisualizationLoadedEvent = createVisualizationLoadedEvent;
