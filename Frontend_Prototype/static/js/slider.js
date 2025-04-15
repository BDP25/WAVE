import { fetchVisualization } from "./api.js";

export function createDateSliderWithPicker(container, history, article_id) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    const sortedHistory = history.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const newestEntry = lastEntry;
    const seventnewestEntry = sortedHistory.length >= 10
        ? sortedHistory[sortedHistory.length - 10]
        : sortedHistory[0];

    const timelineAxis = createTimelineAxis(firstEntry.timestamp, lastEntry.timestamp);
    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    if (slider.noUiSlider) slider.noUiSlider.destroy();

    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(seventnewestEntry.timestamp).getTime();
    const sliderEnd = new Date(newestEntry.timestamp).getTime();

    noUiSlider.create(slider, {
        start: [sliderStart, sliderEnd],
        connect: true,
        range: {
            min: fullRangeStart,
            max: fullRangeEnd
        },
        step: 24 * 60 * 60 * 1000,
        tooltips: [
            {
                to: (value) => formatDate(new Date(+value)),
                from: Number
            },
            {
                to: (value) => formatDate(new Date(+value)),
                from: Number
            }
        ],
        format: {
            to: value => +value,
            from: value => +value
        }
    });

    slider.noUiSlider.on("update", (values, handle) => {
        const tooltip = slider.querySelectorAll(".noUi-tooltip")[handle];
        tooltip.textContent = formatDate(new Date(+values[handle]));
    });

    // Add event listener for slider changes
    slider.noUiSlider.on("change", (values) => {
        const updatedStart = new Date(+values[0]);
        const updatedEnd = new Date(+values[1]);

        const startEntry = history.find(entry => new Date(entry.timestamp).getTime() === updatedStart.getTime());
        const endEntry = history.find(entry => new Date(entry.timestamp).getTime() === updatedEnd.getTime());

        if (!startEntry) {
            console.log(`No matching entry found in history for start date: ${formatDate(updatedStart)}`);
        }
        if (!endEntry) {
            console.log(`No matching entry found in history for end date: ${formatDate(updatedEnd)}`);
        }

        if (startEntry && endEntry) {
            // Trigger a new request with the updated range
            fetchRevidsAndVisualization(history, article_id, endEntry, startEntry);
        }
    });

    fetchRevidsAndVisualization(history, article_id, newestEntry, seventnewestEntry);
    setupSliderTooltips(slider, seventnewestEntry, newestEntry, article_id, history);
}

function formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function createTimelineAxis(startDate, endDate) {
    const timelineAxis = document.createElement("div");
    timelineAxis.className = "timeline-axis";

    const start = new Date(startDate);
    const end = new Date(endDate);
    const yearRange = end.getFullYear() - start.getFullYear();

    if (yearRange <= 2) {
        addYearAndMonthLabels(timelineAxis, start, end);
    } else if (yearRange <= 10) {
        addYearLabels(timelineAxis, start, end, 1);
    } else {
        addYearLabels(timelineAxis, start, end, 5);
    }

    return timelineAxis;
}

function addYearAndMonthLabels(axis, startDate, endDate) {
    const startYear = startDate.getFullYear();
    const endYear = endDate.getFullYear();

    for (let year = startYear; year <= endYear; year++) {
        const label = document.createElement("span");
        label.className = "year-label";
        label.textContent = year.toString();
        axis.appendChild(label);

        // Add month labels for each year
        const monthStart = year === startYear ? startDate.getMonth() : 0;
        const monthEnd = year === endYear ? endDate.getMonth() : 11;

        for (let month = monthStart; month <= monthEnd; month++) {
            const monthLabel = document.createElement("span");
            monthLabel.className = "month-label";
            monthLabel.textContent = new Date(year, month).toLocaleString('default', { month: 'short' });
            axis.appendChild(monthLabel);
        }
    }
}

function addYearLabels(axis, startDate, endDate, step) {
    const startYear = startDate.getFullYear();
    const endYear = endDate.getFullYear();

    for (let year = startYear; year <= endYear; year += step) {
        const label = document.createElement("span");
        label.className = "year-label";
        label.textContent = year.toString();
        axis.appendChild(label);
    }
}

function fetchRevidsAndVisualization(history, article_id, newestTimestamp, tenthNewestTimestamp) {
    const startRevid = newestTimestamp.revid;
    const endRevid = tenthNewestTimestamp.revid;

    const sliderWrapper = document.querySelector(".slider-wrapper");

    // Clear previous content
    const existingOutputContainer = sliderWrapper.querySelector(".output-container");
    const existingErrorContainer = sliderWrapper.querySelector(".error-container");
    if (existingOutputContainer) existingOutputContainer.remove();
    if (existingErrorContainer) existingErrorContainer.remove();

    fetchVisualization(article_id, startRevid, endRevid)
        .then((data) => {
            console.log(data);
            const outputContainer = document.createElement("div");
            outputContainer.className = "output-container";
            outputContainer.innerHTML = data.html || "<p>No visualization data available.</p>";
            sliderWrapper.appendChild(outputContainer);
        })
        .catch((err) => {
            console.error("Error fetching visualization data:", err);

            const errorContainer = document.createElement("div");
            errorContainer.className = "error-container";
            errorContainer.innerHTML = "<p>Error loading visualization data.</p>";
            sliderWrapper.appendChild(errorContainer);
        });
}


function setupSliderTooltips(slider, seventnewestEntry, newestEntry, articleId, history) {
    const tooltips = slider.querySelectorAll(".noUi-tooltip");

    tooltips.forEach((tooltip, index) => {
        tooltip.style.cursor = "pointer";

        tooltip.addEventListener("click", () => {
            const input = document.createElement("input");
            input.type = "date";
            input.className = "date-picker-input";

            // Get the current slider handle value and set it as the date picker's value
            const currentTimestamp = slider.noUiSlider.get()[index];
            input.value = new Date(+currentTimestamp).toISOString().split("T")[0];

            const rect = tooltip.getBoundingClientRect();
            input.style.position = "absolute";
            input.style.left = `${rect.left}px`;
            input.style.top = `${rect.bottom + window.scrollY + 5}px`;

            input.addEventListener("change", () => {
                const selectedDate = new Date(input.value).getTime();
                slider.noUiSlider.setHandle(index, selectedDate);

                // Update the slider's range and fetch new data
                const updatedStart = slider.noUiSlider.get()[0];
                const updatedEnd = slider.noUiSlider.get()[1];
                const startEntry = history.find(entry => new Date(entry.timestamp).getTime() === +updatedStart);
                const endEntry = history.find(entry => new Date(entry.timestamp).getTime() === +updatedEnd);

                if (!startEntry) {
                    console.log(`No matching entry found in history for start date: ${formatDate(new Date(+updatedStart))}`);
                }
                if (!endEntry) {
                    console.log(`No matching entry found in history for end date: ${formatDate(new Date(+updatedEnd))}`);
                }

                if (startEntry && endEntry) {
                    fetchRevidsAndVisualization(history, articleId, endEntry, startEntry);
                }

                input.remove();
            });

            document.body.appendChild(input);
            input.focus();

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
}