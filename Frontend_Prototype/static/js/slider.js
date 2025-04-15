import { fetchVisualization } from "./api.js";

export function createDateSliderWithPicker(container, history, article_id) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    // Sort history chronologically
    const sortedHistory = history.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const newestEntry = lastEntry;
    const seventnewestEntry = sortedHistory.length >= 10
        ? sortedHistory[sortedHistory.length - 10]
        : sortedHistory[0];

    // Create timeline axis showing FULL range (first to last entry)
    const timelineAxis = createTimelineAxis(
        firstEntry.timestamp,
        lastEntry.timestamp
    );
    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    if (slider.noUiSlider) slider.noUiSlider.destroy();

    // Convert timestamps to milliseconds
    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(seventnewestEntry.timestamp).getTime();
    const sliderEnd = new Date(newestEntry.timestamp).getTime();

    noUiSlider.create(slider, {
        start: [sliderStart, sliderEnd], // Initial slider position
        connect: true,
        range: {
            min: fullRangeStart,
            max: fullRangeEnd
        },
        step: 24 * 60 * 60 * 1000, // 1 day steps
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

// Rest of the functions (fetchRevidsAndVisualization, setupSliderTooltips) remain the same

function fetchRevidsAndVisualization(history, article_id, newestTimestamp, tenthNewestTimestamp) {
    const startRevid = newestTimestamp.revid;
    const endRevid = tenthNewestTimestamp.revid;

    fetchVisualization(article_id, startRevid, endRevid)
        .then((data) => {
            const outputContainer = document.createElement("div");
            outputContainer.className = "output-container";
            outputContainer.innerHTML = data.html || "<p>No visualization data available.</p>";

            const sliderWrapper = document.querySelector(".slider-wrapper");
            sliderWrapper.appendChild(outputContainer);
        })
        .catch((err) => {
            console.error("Error fetching visualization data:", err);

            const errorContainer = document.createElement("div");
            errorContainer.className = "error-container";
            errorContainer.innerHTML = "<p>Error loading visualization data.</p>";

            const sliderWrapper = document.querySelector(".slider-wrapper");
            sliderWrapper.appendChild(errorContainer);
        });
}

function setupSliderTooltips(slider, seventnewestEntry, maxYear, isSingleYear, articleId, history) {
    const tooltips = slider.querySelectorAll(".noUi-tooltip");

    tooltips.forEach((tooltip, index) => {
        tooltip.style.cursor = "pointer";

        tooltip.addEventListener("click", () => {
            const input = document.createElement("input");
            input.type = "date";
            input.className = "date-picker-input";
            const timestamp = index === 0 ? seventnewestEntry.timestamp : history[history.length - 1].timestamp;
            input.value = new Date(timestamp).toISOString().split("T")[0];

            const rect = tooltip.getBoundingClientRect();
            input.style.position = "absolute";
            input.style.left = `${rect.left}px`;
            input.style.top = `${rect.bottom + window.scrollY + 5}px`;

            input.addEventListener("change", () => {
                const selectedDate = new Date(input.value);
                const newValue = isSingleYear ? selectedDate.getMonth() : selectedDate.getTime();
                slider.noUiSlider.setHandle(index, newValue);
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
