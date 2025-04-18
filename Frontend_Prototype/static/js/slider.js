import { fetchVisualization } from "./api.js";

let debounceTimeout;
let currentRequestController = null;
let isInCooldown = false;

// 🆕 Neue Variablen zur Vermeidung redundanter Requests
let lastStartRevid = null;
let lastEndRevid = null;

export function createDateSliderWithPicker(container, history, articleId) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    const sortedHistory = [...history].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    console.log("✅ Sortierte History:");
    console.table(sortedHistory);

    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const tenthNewestEntry = sortedHistory[Math.max(0, sortedHistory.length - 10)];

    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(tenthNewestEntry.timestamp).getTime();
    const sliderEnd = new Date(lastEntry.timestamp).getTime();

    lastStartRevid = tenthNewestEntry.revid;
    lastEndRevid = lastEntry.revid;

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
        clearTimeout(debounceTimeout);

        debounceTimeout = setTimeout(() => {
            const [start, end] = slider.noUiSlider.get().map(Number);
            const startEntry = findClosestEntry(history, start);
            const endEntry = findClosestEntry(history, end);

            // ✅ Nur Request senden, wenn sich die Daten wirklich geändert haben
            if (
                startEntry &&
                endEntry &&
                (startEntry.revid !== lastStartRevid || endEntry.revid !== lastEndRevid)
            ) {
                lastStartRevid = startEntry.revid;
                lastEndRevid = endEntry.revid;
                updateVisualization(sliderWrapper, articleId, startEntry, endEntry);
            } else {
                console.log("Datum gleich geblieben – kein neuer Request.");
            }
        }, 100);
    };

    slider.noUiSlider.on("change", handleSliderChange);
    setupSliderTooltips(slider, history, articleId, handleSliderChange);

    // 🆕 Direkt initialisieren & merken
    updateVisualization(sliderWrapper, articleId, tenthNewestEntry, lastEntry);
    lastStartRevid = tenthNewestEntry.revid;
    lastEndRevid = lastEntry.revid;
}

function updateVisualization(sliderWrapper, articleId, startEntry, endEntry) {
    if (isInCooldown) {
        console.log("Cooldown aktiv – Request blockiert.");
        return;
    }

    if (currentRequestController) {
        console.log("Vorheriger Request wird abgebrochen.");
        currentRequestController.abort();
    }

    currentRequestController = new AbortController();
    const { signal } = currentRequestController;

    removeExistingOutput(sliderWrapper);
    console.log("Request startet...");

    isInCooldown = true;
    setTimeout(() => {
        isInCooldown = false;
    }, 1500);

    fetchVisualization(articleId, endEntry.revid, startEntry.revid, signal)
        .then(data => {
            if (signal.aborted) {
                console.log("Request wurde abgebrochen.");
                return;
            }

            const output = document.createElement("div");
            output.className = "output-container";
            output.innerHTML = data.html || "<p>No visualization data available.</p>";
            sliderWrapper.appendChild(output);
        })
        .catch(err => {
            if (err.name === "AbortError") {
                console.log("Fetch wurde abgebrochen.");
                return;
            }
            console.error("Fehler beim Laden der Visualisierung:", err);
            const error = document.createElement("div");
            error.className = "error-container";
            error.innerHTML = "<p>Fehler beim Laden der Visualisierung.</p>";
            sliderWrapper.appendChild(error);
        });
}

function removeExistingOutput(wrapper) {
    wrapper.querySelectorAll(".output-container, .error-container").forEach(el => el.remove());
}




function setupSliderTooltips(slider, history, articleId, onChange) {
    const firstEntryDate = new Date(history[0].timestamp);
    const lastEntryDate = new Date(history[history.length - 1].timestamp);

    // ✅ Einheitlich mit formatDate arbeiten
    const validDates = history.map(entry => formatDate(new Date(entry.timestamp)));

    const tooltips = slider.querySelectorAll(".noUi-tooltip");
    const calendars = new Array(tooltips.length).fill(null);

    tooltips.forEach((tooltip, index) => {
        tooltip.style.cursor = "pointer";

        tooltip.addEventListener("click", (e) => {
            e.stopImmediatePropagation();
            e.preventDefault();

            if (tooltip.classList.contains("calendar-open")) return;
            tooltip.classList.add("calendar-open");

            const currentSliderValue = slider.noUiSlider.get()[index];

            const fp = flatpickr(tooltip, {
                defaultDate: new Date(+currentSliderValue),
                minDate: firstEntryDate,
                maxDate: lastEntryDate,
                inline: true,
                clickOpens: false,
                dateFormat: "Y-m-d",

                // ✅ Datumsvergleich korrekt formatieren
                disable: [
                    function (date) {
                        const dateStr = formatDate(date);
                        return !validDates.includes(dateStr);
                    }
                ],
                onDayCreate: function (dObj, dStr, fpInstance, dayElem) {
                    const dateStr = formatDate(dayElem.dateObj);
                    if (validDates.includes(dateStr)) {
                        dayElem.classList.add("valid-entry-day");
                    }
                },
                onChange: function (selectedDates) {
                    const newDate = selectedDates[0].getTime();
                    if (newDate !== +currentSliderValue) {
                        slider.noUiSlider.setHandle(index, newDate);
                        onChange();
                    }

                    fp.destroy();
                    tooltip.classList.remove("calendar-open");
                    calendars[index] = null;
                    document.removeEventListener("mousedown", closeCalendar);
                },
                onReady: function (_, __, instance) {
                    const calendar = instance.calendarContainer;
                    calendar.classList.add("small-flatpickr");

                    setTimeout(() => {
                        const rect = calendar.getBoundingClientRect();
                        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

                        if (rect.right > viewportWidth) {
                            const overflow = rect.right - viewportWidth + 80;
                            calendar.style.left = `${calendar.offsetLeft - overflow}px`;
                        }
                    }, 0);
                }
            });

            calendars[index] = fp;
            fp.jumpToDate(new Date(+currentSliderValue));

            function closeCalendar(event) {
                const calendarElement = fp.calendarContainer;
                if (!calendarElement || (!tooltip.contains(event.target) && !calendarElement.contains(event.target))) {
                    fp.destroy();
                    tooltip.classList.remove("calendar-open");
                    calendars[index] = null;
                    document.removeEventListener("mousedown", closeCalendar);
                }
            }

            setTimeout(() => {
                document.addEventListener("mousedown", closeCalendar);
            }, 0);
        });
    });

    slider.noUiSlider.on("slide", () => {
        calendars.forEach((fpInstance, index) => {
            if (fpInstance) {
                fpInstance.destroy();
                tooltips[index].classList.remove("calendar-open");
                calendars[index] = null;
            }
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