import { fetchVisualization } from "./api.js";
let debounceTimeout;

export function createDateSliderWithPicker(container, history, articleId) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    const sortedHistory = [...history].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const tenthNewestEntry = sortedHistory[Math.max(0, sortedHistory.length - 10)];

    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(tenthNewestEntry.timestamp).getTime();
    const sliderEnd = new Date(lastEntry.timestamp).getTime();

    const timelineAxis = createTimelineAxis(firstEntry.timestamp, lastEntry.timestamp);
    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    if (slider.noUiSlider) slider.noUiSlider.destroy();

    noUiSlider.create(slider, {
        start: [sliderStart, sliderEnd],
        connect: true,
        range: { min: fullRangeStart, max: fullRangeEnd },
        step: 24 * 60 * 60 * 1000,
        tooltips: [
            { to: value => formatDate(new Date(+value)), from: Number },
            { to: value => formatDate(new Date(+value)), from: Number }
        ],
        format: {
            to: value => +value,
            from: value => +value
        }
    });

    slider.noUiSlider.on("update", (values, handle) => {
        slider.querySelectorAll(".noUi-tooltip")[handle].textContent = formatDate(new Date(+values[handle]));
    });

    const handleSliderChange = () => {
    clearTimeout(debounceTimeout); // Clear any existing timeout

    debounceTimeout = setTimeout(() => {
        const [start, end] = slider.noUiSlider.get().map(Number);
        const startEntry = findClosestEntry(history, start);
        const endEntry = findClosestEntry(history, end);
        if (startEntry && endEntry) {
            updateVisualization(sliderWrapper, articleId, startEntry, endEntry);
        }
    }, 50); // 50ms delay
};

    slider.noUiSlider.on("change", handleSliderChange);
    setupSliderTooltips(slider, history, articleId, handleSliderChange);

    updateVisualization(sliderWrapper, articleId, tenthNewestEntry, lastEntry);
}


function updateVisualization(sliderWrapper, articleId, startEntry, endEntry) {
    removeExistingOutput(sliderWrapper);

    fetchVisualization(articleId, endEntry.revid, startEntry.revid)
        .then(data => {
            const output = document.createElement("div");
            console.log("Response data:");
            output.className = "output-container";
            output.innerHTML = data.html || "<p>No visualization data available.</p>";
            sliderWrapper.appendChild(output);
        })
        .catch(err => {
            console.error("Error fetching visualization data:", err);
            const error = document.createElement("div");
            error.className = "error-container";
            error.innerHTML = "<p>Error loading visualization data.</p>";
            sliderWrapper.appendChild(error);
        });
}

function removeExistingOutput(wrapper) {
    wrapper.querySelectorAll(".output-container, .error-container").forEach(el => el.remove());
}


function setupSliderTooltips(slider, history, articleId, onChange) {
    slider.querySelectorAll(".noUi-tooltip").forEach((tooltip, index) => {
        tooltip.style.cursor = "pointer";

        tooltip.addEventListener("click", (e) => {
            // Verhindere sofortige Änderung oder Request-Ausführung
            e.stopImmediatePropagation();
            e.preventDefault();

            const input = document.createElement("input");
            input.type = "date";
            input.className = "date-picker-input";

            const currentTimestamp = slider.noUiSlider.get()[index];
            input.value = new Date(+currentTimestamp).toISOString().split("T")[0];

            const rect = tooltip.getBoundingClientRect();
            input.style.position = "absolute";
            input.style.left = `${rect.left}px`;
            input.style.top = `${rect.bottom + window.scrollY + 5}px`;
            input.style.zIndex = "9999";

            // Warten bis der Benutzer das Datum auswählt
            input.addEventListener("change", () => {
                const newDate = new Date(input.value).getTime();
                const currentSliderValue = Number(slider.noUiSlider.get()[index]);

                if (newDate !== currentSliderValue) {
                    slider.noUiSlider.setHandle(index, newDate); // Manuelle Slider-Anpassung
                }

                // Verhindere den Request beim Öffnen des Datepickers
                setTimeout(() => {
                    onChange(); // Erst wenn der Benutzer den Datepicker verlassen hat
                }, 0);

                input.remove(); // Entferne das Eingabefeld nach der Auswahl
            });

            // Datepicker anzeigen
            document.body.appendChild(input);
            input.focus();

            // Klick außerhalb des Inputs entfernt ihn
            const removeOnClickOutside = e => {
                if (!input.contains(e.target) && e.target !== tooltip) {
                    input.remove();
                    document.removeEventListener("click", removeOnClickOutside);
                }
            };

            setTimeout(() => document.addEventListener("click", removeOnClickOutside), 0);
        });
    });
}


function formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function findClosestEntry(history, timestamp) {
    return history.reduce((closest, entry) => {
        const entryTime = new Date(entry.timestamp).getTime();
        const closestTime = new Date(closest.timestamp).getTime();
        return Math.abs(entryTime - timestamp) < Math.abs(closestTime - timestamp) ? entry : closest;
    });
}


function createTimelineAxis(startDate, endDate) {
    const axis = document.createElement("div");
    axis.className = "timeline-axis";

    const start = new Date(startDate);
    const end = new Date(endDate);
    const range = end.getTime() - start.getTime();

    const addLabel = (date, text, className) => {
        const label = document.createElement("span");
        label.className = className;
        label.textContent = text;

        const offset = ((date.getTime() - start.getTime()) / range) * 100;
        label.style.left = `${offset}%`;

        axis.appendChild(label);
    };

    const yearsDiff = end.getFullYear() - start.getFullYear();

    if (yearsDiff <= 2) {
        for (let year = start.getFullYear(); year <= end.getFullYear(); year++) {
            for (let month = 0; month < 12; month++) {
                const current = new Date(year, month);
                if (current >= start && current <= end) {
                    const monthLabel = current.toLocaleString("default", { month: "short" });
                    addLabel(current, monthLabel, "month-label");
                }
            }
            const yearLabelDate = new Date(year, 0, 1);
            if (yearLabelDate >= start && yearLabelDate <= end) {
                addLabel(yearLabelDate, year.toString(), "year-label");
            }
        }
    } else {
        const step = yearsDiff <= 10 ? 1 : 5;
        for (let year = start.getFullYear(); year <= end.getFullYear(); year += step) {
            const labelDate = new Date(year, 0, 1);
            addLabel(labelDate, year.toString(), "year-label");
        }
    }

    return axis;
}





