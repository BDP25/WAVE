import { fetchVisualization } from "./api.js";

let debounceTimeout;
let currentRequestController = null;
let lastStartRevid = null;
let lastEndRevid = null;

export function createDateSliderWithPicker(container, history, articleId) {
    container.innerHTML = "";
    const { sliderWrapper, slider } = createSliderElements(container);
    const sortedHistory = [...history].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    console.log("✅ Sortierte History:");
    console.table(sortedHistory);

    const { firstEntry, lastEntry, tenthNewestEntry } = getKeyEntries(sortedHistory);
    const { fullRangeStart, fullRangeEnd, sliderStart, sliderEnd } = calculateTimeRanges(firstEntry, lastEntry, tenthNewestEntry);

    lastStartRevid = tenthNewestEntry.revid;
    lastEndRevid = lastEntry.revid;

    appendTimelineAxis(sliderWrapper, firstEntry.timestamp, lastEntry.timestamp);

    initializeSlider(slider, fullRangeStart, fullRangeEnd, sliderStart, sliderEnd, sortedHistory);

    const handleSliderChange = createSliderChangeHandler(slider, history, sliderWrapper, articleId);
    slider.noUiSlider.on("change", handleSliderChange);

    setupSliderTooltips(slider, history, articleId, handleSliderChange);

    // Initial visualization
    updateVisualization(sliderWrapper, articleId, tenthNewestEntry, lastEntry);
    lastStartRevid = tenthNewestEntry.revid;
    lastEndRevid = lastEntry.revid;
}

function createSliderElements(container) {
    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    container.appendChild(sliderWrapper);

    return { sliderWrapper, slider };
}

function getKeyEntries(sortedHistory) {
    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const tenthNewestEntry = sortedHistory[Math.max(0, sortedHistory.length - 10)];

    return { firstEntry, lastEntry, tenthNewestEntry };
}

function calculateTimeRanges(firstEntry, lastEntry, tenthNewestEntry) {
    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(tenthNewestEntry.timestamp).getTime();
    const sliderEnd = new Date(lastEntry.timestamp).getTime();

    return { fullRangeStart, fullRangeEnd, sliderStart, sliderEnd };
}

function appendTimelineAxis(sliderWrapper, startDate, endDate) {
    const timelineAxis = createTimelineAxis(startDate, endDate);
    sliderWrapper.appendChild(timelineAxis);
}

function initializeSlider(slider, fullRangeStart, fullRangeEnd, sliderStart, sliderEnd, sortedHistory) {
    if (slider.noUiSlider) slider.noUiSlider.destroy();

    const validTimestamps = extractValidTimestamps(sortedHistory);

    createSliderWithOptions(slider, fullRangeStart, fullRangeEnd, sliderStart, sliderEnd);
    configureSliderSnapping(slider, validTimestamps);
    configureSliderTooltipUpdates(slider);
}

function extractValidTimestamps(sortedHistory) {
    return sortedHistory.map(entry => new Date(entry.timestamp).getTime());
}

function createSliderWithOptions(slider, fullRangeStart, fullRangeEnd, sliderStart, sliderEnd) {
    noUiSlider.create(slider, {
        start: [sliderStart, sliderEnd],
        connect: true,
        range: { min: fullRangeStart, max: fullRangeEnd },
        step: null, // Remove fixed step to allow snapping to exact dates
        tooltips: [
            { to: value => formatDate(new Date(+value)), from: Number },
            { to: value => formatDate(new Date(+value)), from: Number }
        ],
        format: {
            to: value => +value,
            from: value => +value
        }
    });
}

function configureSliderSnapping(slider, validTimestamps) {
    slider.noUiSlider.on("set", (values, handle) => {
        const value = Number(values[handle]);
        const closestTimestamp = findClosestTimestamp(validTimestamps, value);

        if (value !== closestTimestamp) {
            const newValues = [...slider.noUiSlider.get().map(Number)];
            newValues[handle] = closestTimestamp;
            slider.noUiSlider.set(newValues);
        }
    });
}

function configureSliderTooltipUpdates(slider) {
    slider.noUiSlider.on("update", (values, handle) => {
        slider.querySelectorAll(".noUi-tooltip")[handle].textContent = formatDate(new Date(+values[handle]));
    });
}

function createSliderChangeHandler(slider, history, sliderWrapper, articleId) {
    return () => {
        clearTimeout(debounceTimeout);

        debounceTimeout = setTimeout(() => {
            const [start, end] = slider.noUiSlider.get().map(Number);
            const nearestStart = findClosestEntry(history, start);
            const nearestEnd = findClosestEntry(history, end);

            const nearestStartTime = new Date(nearestStart.timestamp).getTime();
            const nearestEndTime = new Date(nearestEnd.timestamp).getTime();

            if (shouldUpdateVisualization(nearestStart, nearestEnd)) {
                updateRevidValues(nearestStart, nearestEnd);
                smoothSliderSet(slider, start, nearestStartTime, end, nearestEndTime);
                updateVisualization(sliderWrapper, articleId, nearestStart, nearestEnd);
            } else {
                console.log("Datum gleich geblieben – kein neuer Request.");
                smoothSliderSet(slider, start, nearestStartTime, end, nearestEndTime);
            }
        }, 100);
    };
}

function shouldUpdateVisualization(nearestStart, nearestEnd) {
    return nearestStart &&
           nearestEnd &&
           (nearestStart.revid !== lastStartRevid || nearestEnd.revid !== lastEndRevid);
}

function updateRevidValues(nearestStart, nearestEnd) {
    lastStartRevid = nearestStart.revid;
    lastEndRevid = nearestEnd.revid;
}

function smoothSliderSet(slider, currentStart, targetStart, currentEnd, targetEnd, steps = 10) {
    const startDiff = (targetStart - currentStart) / steps;
    const endDiff = (targetEnd - currentEnd) / steps;
    let step = 0;

    function animateStep() {
        if (step <= steps) {
            const newStart = currentStart + step * startDiff;
            const newEnd = currentEnd + step * endDiff;
            slider.noUiSlider.set([newStart, newEnd]);
            step++;
            requestAnimationFrame(animateStep);
        }
    }

    animateStep();
}

function updateVisualization(sliderWrapper, articleId, startEntry, endEntry) {
    cancelExistingRequest();

    currentRequestController = new AbortController();
    const { signal } = currentRequestController;

    removeExistingOutput(sliderWrapper);
    console.log("Request startet...");

    fetchVisualizationData(articleId, endEntry, startEntry, signal, sliderWrapper);
}

function cancelExistingRequest() {
    if (currentRequestController) {
        console.log("Vorheriger Request wird abgebrochen.");
        currentRequestController.abort();
    }
}

function fetchVisualizationData(articleId, endEntry, startEntry, signal, sliderWrapper) {
    fetchVisualization(articleId, endEntry.revid, startEntry.revid, signal)
        .then(data => {
            if (signal.aborted) {
                console.log("Request wurde abgebrochen.");
                return;
            }
            displayVisualizationOutput(data, sliderWrapper);
        })
        .catch(err => handleVisualizationError(err, sliderWrapper));
}

function displayVisualizationOutput(data, sliderWrapper) {
    const output = document.createElement("div");
    output.className = "output-container";
    output.innerHTML = data.html || "<p>No visualization data available.</p>";
    sliderWrapper.appendChild(output);
}

function handleVisualizationError(err, sliderWrapper) {
    if (err.name === "AbortError") {
        console.log("Fetch wurde abgebrochen.");
        return;
    }
    console.error("Fehler beim Laden der Visualisierung:", err);

    const error = document.createElement("div");
    error.className = "error-container";
    error.innerHTML = "<p>Fehler beim Laden der Visualisierung.</p>";
    sliderWrapper.appendChild(error);
}

function removeExistingOutput(wrapper) {
    wrapper.querySelectorAll(".output-container, .error-container").forEach(el => el.remove());
}

function setupSliderTooltips(slider, history, articleId, onChange) {
    const { firstEntryDate, lastEntryDate, validDates, dateToEntryMap } = prepareTooltipData(history);

    const tooltips = slider.querySelectorAll(".noUi-tooltip");
    const calendars = new Array(tooltips.length).fill(null);

    configureTooltipPositioning(slider, tooltips);
    setupTooltipEventListeners(tooltips, slider, calendars, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, onChange);

    // Initialize tooltip positions
    setTimeout(() => adjustTooltipPositions(tooltips), 0);
}

function prepareTooltipData(history) {
    const firstEntryDate = new Date(history[0].timestamp);
    const lastEntryDate = new Date(history[history.length - 1].timestamp);
    const validDates = history.map(entry => formatDate(new Date(entry.timestamp)));

    const dateToEntryMap = {};
    history.forEach(entry => {
        const dateStr = formatDate(new Date(entry.timestamp));
        dateToEntryMap[dateStr] = entry;
    });

    return { firstEntryDate, lastEntryDate, validDates, dateToEntryMap };
}

function configureTooltipPositioning(slider, tooltips) {
    slider.noUiSlider.on('update', () => adjustTooltipPositions(tooltips));
}

function adjustTooltipPositions(tooltips) {
    if (tooltips.length < 2) return;

    const tooltip1 = tooltips[0];
    const tooltip2 = tooltips[1];

    resetTooltipPositions(tooltip1, tooltip2);
    const { rect1, rect2, viewportWidth } = getTooltipMeasurements(tooltip1, tooltip2);
    const { rightEdgeMargin, minSpace } = getTooltipSpacingSettings();

    handleRightEdgeCase(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace);
}

function resetTooltipPositions(tooltip1, tooltip2) {
    tooltip1.style.transform = '';
    tooltip2.style.transform = '';

    // Force layout recalculation
    void tooltip1.offsetWidth;
    void tooltip2.offsetWidth;
}

function getTooltipMeasurements(tooltip1, tooltip2) {
    const rect1 = tooltip1.getBoundingClientRect();
    const rect2 = tooltip2.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

    return { rect1, rect2, viewportWidth };
}

function getTooltipSpacingSettings() {
    return {
        rightEdgeMargin: 50, // Margin from right edge
        minSpace: 25 // Minimum space between tooltips
    };
}

function handleRightEdgeCase(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace) {
    if (rect2.right > viewportWidth - rightEdgeMargin) {
        handleRightEdgeOverflow(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace);
    } else {
        handleNormalOverlapCase(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace);
    }

    performFinalRightEdgeCheck(tooltip1, tooltip2, rect1, viewportWidth, rightEdgeMargin, minSpace);
}

function handleRightEdgeOverflow(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace) {
    const moveLeft2 = rect2.right - (viewportWidth - rightEdgeMargin);

    tooltip2.style.transform = `translateX(-${moveLeft2}px)`;

    void tooltip2.offsetWidth;
    const updatedRect2 = tooltip2.getBoundingClientRect();

    if (rect1.right + minSpace > updatedRect2.left) {
        const overlapAmount = rect1.right + minSpace - updatedRect2.left;
        tooltip1.style.transform = `translateX(-${overlapAmount}px)`;
    }
}

function handleNormalOverlapCase(tooltip1, tooltip2, rect1, rect2, viewportWidth, rightEdgeMargin, minSpace) {
    const overlap = rect1.right + minSpace > rect2.left;

    if (overlap) {
        const overlapAmount = rect1.right + minSpace - rect2.left;
        const availableRightSpace = viewportWidth - rightEdgeMargin - rect2.right;

        if (availableRightSpace >= overlapAmount/2) {
            distributeOverlapEvenly(tooltip1, tooltip2, overlapAmount);
        } else {
            handleLimitedRightSpace(tooltip1, tooltip2, overlapAmount, availableRightSpace);
        }
    }
}

function distributeOverlapEvenly(tooltip1, tooltip2, overlapAmount) {
    tooltip1.style.transform = `translateX(-${overlapAmount/2}px)`;
    tooltip2.style.transform = `translateX(${overlapAmount/2}px)`;
}

function handleLimitedRightSpace(tooltip1, tooltip2, overlapAmount, availableRightSpace) {
    const moveRight2 = availableRightSpace > 0 ? availableRightSpace : 0;
    const moveLeft1 = overlapAmount - moveRight2;

    tooltip1.style.transform = `translateX(-${moveLeft1}px)`;

    if (moveRight2 > 0) {
        tooltip2.style.transform = `translateX(${moveRight2}px)`;
    }
}

function performFinalRightEdgeCheck(tooltip1, tooltip2, rect1, viewportWidth, rightEdgeMargin, minSpace) {
    void tooltip2.offsetWidth;
    const finalRect2 = tooltip2.getBoundingClientRect();

    if (finalRect2.right > viewportWidth - rightEdgeMargin) {
        const additionalAdjustment = finalRect2.right - (viewportWidth - rightEdgeMargin);
        applyAdditionalRightAdjustment(tooltip1, tooltip2, rect1, additionalAdjustment, minSpace);
    }
}

function applyAdditionalRightAdjustment(tooltip1, tooltip2, rect1, additionalAdjustment, minSpace) {
    const currentLeftShift = extractCurrentTransformValue(tooltip2);

    tooltip2.style.transform = `translateX(-${currentLeftShift + additionalAdjustment}px)`;

    void tooltip2.offsetWidth;
    const adjustedRect2 = tooltip2.getBoundingClientRect();

    if (rect1.right + minSpace > adjustedRect2.left) {
        applyAdditionalTooltip1Adjustment(tooltip1, rect1, adjustedRect2, minSpace);
    }
}

function extractCurrentTransformValue(tooltip) {
    let currentShift = 0;
    const currentTransform = tooltip.style.transform;

    if (currentTransform.includes('translateX(-')) {
        currentShift = parseFloat(currentTransform.match(/translateX\(-([^)]+)\)/)[1]);
    } else if (currentTransform.includes('translateX(')) {
        tooltip.style.transform = '';
        void tooltip.offsetWidth;
    }

    return currentShift;
}

function applyAdditionalTooltip1Adjustment(tooltip1, rect1, adjustedRect2, minSpace) {
    const newOverlap = rect1.right + minSpace - adjustedRect2.left;
    const currentTooltip1Shift = extractCurrentTransformValue(tooltip1);

    tooltip1.style.transform = `translateX(-${currentTooltip1Shift + newOverlap}px)`;
}

function setupTooltipEventListeners(tooltips, slider, calendars, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, onChange) {
    tooltips.forEach((tooltip, index) => {
        tooltip.style.cursor = "pointer";
        tooltip.addEventListener("click", (e) => handleTooltipClick(e, tooltip, index, slider, calendars, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, onChange, tooltips));
    });

    setupSlideEventHandler(slider, calendars, tooltips);
}

function handleTooltipClick(e, tooltip, index, slider, calendars, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, onChange, tooltips) {
    e.stopImmediatePropagation();
    e.preventDefault();

    if (tooltip.classList.contains("calendar-open")) return;
    tooltip.classList.add("calendar-open");

    const currentSliderValue = slider.noUiSlider.get()[index];
    const currentDate = new Date(+currentSliderValue);

    const fp = createFlatpickrInstance(tooltip, currentDate, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, index, slider, onChange, calendars, tooltips);

    calendars[index] = fp;
    fp.jumpToDate(currentDate);

    setupCalendarCloseHandler(fp, tooltip, index, calendars, tooltips);
}

function createFlatpickrInstance(tooltip, currentDate, firstEntryDate, lastEntryDate, validDates, dateToEntryMap, index, slider, onChange, calendars, tooltips) {
    return flatpickr(tooltip, {
        defaultDate: currentDate,
        minDate: firstEntryDate,
        maxDate: lastEntryDate,
        inline: true,
        clickOpens: false,
        dateFormat: "Y-m-d",
        disable: [date => !validDates.includes(formatDate(date))],
        onDayCreate: (dObj, dStr, fpInstance, dayElem) => {
            const dateStr = formatDate(dayElem.dateObj);
            if (validDates.includes(dateStr)) {
                dayElem.classList.add("valid-entry-day");
            }
        },
        onChange: selectedDates => handleCalendarDateChange(selectedDates, dateToEntryMap, index, slider, onChange, tooltip, calendars, tooltips),
        onReady: (_, __, instance) => positionCalendarContainer(instance)
    });
}

function handleCalendarDateChange(selectedDates, dateToEntryMap, index, slider, onChange, tooltip, calendars, tooltips) {
    const selectedDate = selectedDates[0];
    const dateStr = formatDate(selectedDate);

    console.log("Selected date (local):", selectedDate);
    console.log("Formatted date string:", dateStr);

    if (dateToEntryMap[dateStr]) {
        applyExactTimestamp(dateToEntryMap[dateStr], index, slider, onChange);
    } else {
        handleInvalidDate(selectedDate, index, slider, onChange, history);
    }

    // Get the flatpickr instance before calling closeAndCleanupCalendar
    const fp = calendars[index];
    if (fp) {
        closeAndCleanupCalendar(fp, tooltip, index, calendars, tooltips);
    }
}


function applyExactTimestamp(exactEntry, index, slider, onChange) {
    const exactTimestamp = new Date(exactEntry.timestamp).getTime();
    console.log("Found matching entry with timestamp:", new Date(exactTimestamp).toISOString());

    slider.noUiSlider.setHandle(index, exactTimestamp);
    onChange();
}

function handleInvalidDate(selectedDate, index, slider, onChange) {
    console.log("No matching entry found for date:", formatDate(selectedDate));
    const nearestEntry = findClosestEntry(history, selectedDate.getTime());
    const nearestTime = new Date(nearestEntry.timestamp).getTime();

    slider.noUiSlider.setHandle(index, nearestTime);
    onChange();
}

function closeAndCleanupCalendar(fp, tooltip, index, calendars, tooltips) {
    if (fp) {
        fp.destroy();
        tooltip.classList.remove("calendar-open");
        calendars[index] = null;

        // Use the stored close handler from the flatpickr instance
        if (fp._closeCalendarHandler) {
            document.removeEventListener("mousedown", fp._closeCalendarHandler);
        }
    }

    setTimeout(() => adjustTooltipPositions(tooltips), 0);
}

function positionCalendarContainer(instance) {
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

function setupCalendarCloseHandler(fp, tooltip, index, calendars, tooltips) {
    function closeCalendar(event) {
        const calendarElement = fp.calendarContainer;
        if (!calendarElement || (!tooltip.contains(event.target) && !calendarElement.contains(event.target))) {
            fp.destroy();
            tooltip.classList.remove("calendar-open");
            calendars[index] = null;
            document.removeEventListener("mousedown", closeCalendar);

            // Readjust tooltip positions after calendar closes
            setTimeout(() => adjustTooltipPositions(tooltips), 0);
        }
    }

    // Store the handler on the flatpickr instance
    fp._closeCalendarHandler = closeCalendar;

    setTimeout(() => {
        document.addEventListener("mousedown", closeCalendar);
    }, 0);
}

function setupSlideEventHandler(slider, calendars, tooltips) {
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

function findClosestTimestamp(timestamps, target) {
    return timestamps.reduce((prev, curr) =>
        Math.abs(curr - target) < Math.abs(prev - target) ? curr : prev
    );
}

function createTimelineAxis(startDate, endDate) {
    const axis = document.createElement("div");
    axis.className = "timeline-axis";

    const start = new Date(startDate);
    const end = new Date(endDate);
    const range = end.getTime() - start.getTime();

    const yearsDiff = end.getFullYear() - start.getFullYear();

    if (yearsDiff <= 2) {
        createDetailedTimeAxis(axis, start, end, range);
    } else {
        createYearlyTimeAxis(axis, start, end, range, yearsDiff);
    }

    return axis;
}

function createDetailedTimeAxis(axis, start, end, range) {
    for (let year = start.getFullYear(); year <= end.getFullYear(); year++) {
        addMonthLabels(axis, year, start, end, range);
        addYearLabel(axis, year, start, end, range);
    }
}

function addMonthLabels(axis, year, start, end, range) {
    for (let month = 0; month < 12; month++) {
        const current = new Date(year, month);
        if (current >= start && current <= end) {
            const monthLabel = current.toLocaleString("default", { month: "short" });
            addAxisLabel(axis, current, monthLabel, "month-label", start, range);
        }
    }
}

function addYearLabel(axis, year, start, end, range) {
    const yearLabelDate = new Date(year, 0, 1);
    if (yearLabelDate >= start && yearLabelDate <= end) {
        addAxisLabel(axis, yearLabelDate, year.toString(), "year-label", start, range);
    }
}

function createYearlyTimeAxis(axis, start, end, range, yearsDiff) {
    const step = yearsDiff <= 10 ? 1 : 5;
    for (let year = start.getFullYear(); year <= end.getFullYear(); year += step) {
        const labelDate = new Date(year, 0, 1);
        addAxisLabel(axis, labelDate, year.toString(), "year-label", start, range);
    }
}

function addAxisLabel(axis, date, text, className, start, range) {
    const label = document.createElement("span");
    label.className = className;
    label.textContent = text;

    const offset = ((date.getTime() - start.getTime()) / range) * 100;
    label.style.left = `${offset}%`;

    axis.appendChild(label);
}