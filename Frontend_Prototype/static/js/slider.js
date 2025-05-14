import { fetchVisualization } from "./api.js";

let debounceTimeout;
let currentRequestController = null;
let lastStartRevid = null;
let lastEndRevid = null;


export function createDateSliderWithPicker(container, history, articleId) {
    container.innerHTML = "";
    const { sliderWrapper, slider } = createSliderElements(container);
    const sortedHistory = [...history].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));



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
    configureSliderHandleConstraints(slider, sortedHistory);
}

function configureSliderHandleConstraints(slider, sortedHistory) {
    // Sort timestamps chronologically
    const timestamps = sortedHistory.map(entry => new Date(entry.timestamp).getTime()).sort((a, b) => a - b);

    slider.noUiSlider.on("set", (values, handle) => {
        const currentValue = Number(values[handle]);

        if (handle === 0) { // Left (start) handle
            const rightValue = Number(slider.noUiSlider.get()[1]);

            // Find the next valid timestamp that's less than the right handle
            const validOptions = timestamps.filter(ts => ts < rightValue);
            if (validOptions.length > 0) {
                const closestValue = findClosestTimestamp(validOptions, currentValue);
                if (currentValue !== closestValue) {
                    setTimeout(() => {
                        const newValues = [...slider.noUiSlider.get().map(Number)];
                        newValues[0] = closestValue;
                        slider.noUiSlider.set(newValues);
                    }, 0);
                }
            }
        } else { // Right (end) handle
            const leftValue = Number(slider.noUiSlider.get()[0]);

            // Find the next valid timestamp that's greater than the left handle
            const validOptions = timestamps.filter(ts => ts > leftValue);
            if (validOptions.length > 0) {
                const closestValue = findClosestTimestamp(validOptions, currentValue);
                if (currentValue !== closestValue) {
                    setTimeout(() => {
                        const newValues = [...slider.noUiSlider.get().map(Number)];
                        newValues[1] = closestValue;
                        slider.noUiSlider.set(newValues);
                    }, 0);
                }
            }
        }
    });
}

function setupTooltipEventListeners(tooltips, slider, calendars, firstEntryDate, lastEntryDate, entriesByDate, onChange, tooltips2, history) {
    tooltips.forEach((tooltip, index) => {
        tooltip.classList.add("tooltip-clickable");

        tooltip.addEventListener("click", (e) =>
            handleTooltipClick(
                e,
                tooltip,
                index,
                slider,
                calendars,
                firstEntryDate,
                lastEntryDate,
                entriesByDate,
                onChange,
                tooltips,
                history
            )
        );
    });

    setupSlideEventHandler(slider, calendars, tooltips);
}


function handleCalendarDateChange(selectedDates, entriesByDate, index, slider, onChange, tooltip, calendars, tooltips, history) {
    const selectedDate = selectedDates[0];
    const dateStr = formatDate(selectedDate);

    if (entriesByDate[dateStr]) {
        const entries = entriesByDate[dateStr];
        const fp = calendars[index];

        // Get the current values for both handles
        const sliderValues = slider.noUiSlider.get().map(Number);
        const otherHandleIndex = index === 0 ? 1 : 0;
        const otherHandleValue = sliderValues[otherHandleIndex];

        // Filter entries based on the other handle's constraint
        const constrainedEntries = entries.filter(entry => {
            const entryTimestamp = new Date(entry.timestamp).getTime();

            if (index === 0) { // Left handle - must be less than right handle
                return entryTimestamp < otherHandleValue;
            } else { // Right handle - must be greater than left handle
                return entryTimestamp > otherHandleValue;
            }
        });

        if (constrainedEntries.length === 0) {
            // No valid entries after constraint - show message and don't change
            alert("No valid timestamps available for this date with current constraints");
            // Revert to current date display
            fp.setDate(new Date(sliderValues[index]), true);
            return;
        }

        if (constrainedEntries.length === 1) {
            // Only one entry for this date, apply it directly and close
            applyExactTimestamp(constrainedEntries[0], index, slider, onChange);
            closeAndCleanupCalendar(fp, tooltip, index, calendars, tooltips);
        } else if (fp && fp._timeSelectionContainer) {
            // Multiple valid entries, show time selection dropdown
            showConstrainedTimeSelectionForDate(dateStr, entriesByDate, fp, index, sliderValues[index], slider, onChange, tooltips, tooltip, calendars, otherHandleValue);
        }
    } else {
        handleInvalidDate(selectedDate, index, slider, onChange, history);
        const fp = calendars[index];
        if (fp) {
            closeAndCleanupCalendar(fp, tooltip, index, calendars, tooltips);
        }
    }
}



function showConstrainedTimeSelectionForDate(dateStr, entriesByDate, fp, index, currentSliderValue, slider, onChange, tooltips, tooltip, calendars, otherHandleValue) {
    const entries = entriesByDate[dateStr];
    if (!entries || entries.length <= 1) return 0;

    const timeSelectionContainer = fp._timeSelectionContainer;
    timeSelectionContainer.innerHTML = "";
    timeSelectionContainer.style.display = "block";

    const timeGrid = document.createElement("div");
    timeGrid.className = "time-grid";

    const currentTimestamp = Number(currentSliderValue);
    const sliderHandleValue = Number(slider.noUiSlider.get()[index]);
    const selectedEntry = entries.find(entry =>
        new Date(entry.timestamp).getTime() === sliderHandleValue
    );

    let closestEntry = selectedEntry || entries[0];
    let closestDiff = Math.abs(new Date(closestEntry.timestamp).getTime() - currentTimestamp);
    let validEntriesCount = 0;

    entries.forEach((entry) => {
        const entryTime = new Date(entry.timestamp).getTime();
        const isValidTimestamp = (index === 0) ? entryTime < otherHandleValue : entryTime > otherHandleValue;
        if (!isValidTimestamp) return;

        validEntriesCount++;
        const diff = Math.abs(entryTime - currentTimestamp);
        if (!selectedEntry && diff < closestDiff) {
            closestEntry = entry;
            closestDiff = diff;
        }

        const timeButton = document.createElement("button");
        timeButton.className = "time-entry-button";
        const dateObj = new Date(entry.timestamp);
        timeButton.textContent = dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        const isSelected = selectedEntry && entry.timestamp === selectedEntry.timestamp;
        const isClosest = !selectedEntry && entry === closestEntry;

        if (isSelected || isClosest) {
            timeButton.classList.add("selected");
        }

        timeButton.addEventListener("mouseover", () => {
            if (!isSelected && !isClosest) timeButton.classList.add("hovered");
        });

        timeButton.addEventListener("mouseout", () => {
            timeButton.classList.remove("hovered");
        });

        timeButton.addEventListener("click", () => {
            const exactTimestamp = new Date(entry.timestamp).getTime();
            slider.noUiSlider.setHandle(index, exactTimestamp);
            onChange();
            closeAndCleanupCalendar(fp, tooltip, index, calendars, tooltips);
        });

        timeGrid.appendChild(timeButton);
    });

    if (validEntriesCount === 0) {
        const noValidTimesMsg = document.createElement("p");
        noValidTimesMsg.className = "no-valid-times";
        noValidTimesMsg.textContent = index === 0
            ? "No times available before the end date"
            : "No times available after the start date";
        timeSelectionContainer.appendChild(noValidTimesMsg);
        return 0;
    }

    timeSelectionContainer.appendChild(timeGrid);
    return validEntriesCount;
}


// Replace the existing showTimeSelectionForDate with the constrained version
function showTimeSelectionForDate(dateStr, entriesByDate, fp, index, currentSliderValue, slider, onChange, tooltips, tooltip, calendars) {
    const otherHandleIndex = index === 0 ? 1 : 0;
    const otherHandleValue = Number(slider.noUiSlider.get()[otherHandleIndex]);

    return showConstrainedTimeSelectionForDate(
        dateStr,
        entriesByDate,
        fp,
        index,
        currentSliderValue,
        slider,
        onChange,
        tooltips,
        tooltip,
        calendars,
        otherHandleValue
    );
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

        // Find the closest timestamp based on the handle direction
        let targetTimestamp;
        if (handle === 0) { // Left handle - snap to next higher timestamp
            // Find the nearest timestamp that is greater than or equal to value
            targetTimestamp = validTimestamps
                .filter(ts => ts >= value)
                .sort((a, b) => a - b)[0];

            // If no higher timestamp found, use the closest lower timestamp
            if (!targetTimestamp) {
                targetTimestamp = validTimestamps
                    .filter(ts => ts < value)
                    .sort((a, b) => b - a)[0];
            }
        } else { // Right handle - snap to next lower timestamp
            // Find the nearest timestamp that is less than or equal to value
            targetTimestamp = validTimestamps
                .filter(ts => ts <= value)
                .sort((a, b) => b - a)[0];

            // If no lower timestamp found, use the closest higher timestamp
            if (!targetTimestamp) {
                targetTimestamp = validTimestamps
                    .filter(ts => ts > value)
                    .sort((a, b) => a - b)[0];
            }
        }

        // If we found a target timestamp and it's different from current value
        if (targetTimestamp && value !== targetTimestamp) {
            const newValues = [...slider.noUiSlider.get().map(Number)];
            newValues[handle] = targetTimestamp;
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

    // Trigger the visualization loaded event with a slight delay to ensure DOM is ready
    setTimeout(() => {
        if (window.createVisualizationLoadedEvent) {
            console.log("Triggering visualization loaded event");
            window.createVisualizationLoadedEvent();
        } else {
            console.warn("createVisualizationLoadedEvent function not found");
        }
    }, 100);  // Small delay to ensure content is fully rendered
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
    const { firstEntryDate, lastEntryDate, entriesByDate } = prepareTooltipData(history);

    const tooltips = slider.querySelectorAll(".noUi-tooltip");
    const calendars = new Array(tooltips.length).fill(null);

    configureTooltipPositioning(slider, tooltips);
    setupTooltipEventListeners(tooltips, slider, calendars, firstEntryDate, lastEntryDate, entriesByDate, onChange, tooltips, history);

    // Initialize tooltip positions
    setTimeout(() => adjustTooltipPositions(tooltips), 0);
}

function prepareTooltipData(history) {
    const firstEntryDate = new Date(history[0].timestamp);
    const lastEntryDate = new Date(history[history.length - 1].timestamp);

    // Group entries by date to handle multiple entries per day
    const entriesByDate = {};
    history.forEach(entry => {
        const dateStr = formatDate(new Date(entry.timestamp));
        if (!entriesByDate[dateStr]) {
            entriesByDate[dateStr] = [];
        }
        entriesByDate[dateStr].push(entry);
    });

    // Sort entries within each day by timestamp
    Object.keys(entriesByDate).forEach(dateStr => {
        entriesByDate[dateStr].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    });

    return { firstEntryDate, lastEntryDate, entriesByDate };
}

function configureTooltipPositioning(slider, tooltips) {
    slider.noUiSlider.on('update', () => adjustTooltipPositions(tooltips));
}


function adjustTooltipPositions(tooltips) {
    if (tooltips.length < 2) return;

    const tooltip1 = tooltips[0];
    const tooltip2 = tooltips[1];

    // Reset positions to get true measurements
    tooltip1.style.transform = '';
    tooltip2.style.transform = '';

    // Force reflow to ensure measurements are updated
    void tooltip1.offsetWidth;
    void tooltip2.offsetWidth;

    const rect1 = tooltip1.getBoundingClientRect();
    const rect2 = tooltip2.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

    const rightEdgeMargin = 105; // Margin from the right edge of viewport
    const minSpace = 60; // Minimum space between tooltips

    // First calculate if the right tooltip is out of bounds
    const rightTooltipOverflow = rect2.right > (viewportWidth - rightEdgeMargin);

    // Then calculate if the tooltips are overlapping
    const tooltipsOverlap = rect1.right + minSpace > rect2.left;

    // Handle both cases
    if (rightTooltipOverflow) {
        // First fix the right tooltip's position
        const rightOverflow = rect2.right - (viewportWidth - rightEdgeMargin);
        tooltip2.style.transform = `translateX(-${rightOverflow}px)`;

        // Force reflow again for updated measurements
        void tooltip2.offsetWidth;
        const updatedRect2 = tooltip2.getBoundingClientRect();

        // Check if we now have an overlap after adjusting the right tooltip
        if (rect1.right + minSpace > updatedRect2.left) {
            const overlapAfterRightFix = rect1.right + minSpace - updatedRect2.left;
            tooltip1.style.transform = `translateX(-${overlapAfterRightFix}px)`;
        }
    } else if (tooltipsOverlap) {
        // Handle just the overlap when right tooltip is in bounds
        const overlap = rect1.right + minSpace - rect2.left;

        // Move both tooltips away from each other
        tooltip1.style.transform = `translateX(-${overlap / 2}px)`;
        tooltip2.style.transform = `translateX(${overlap / 2}px)`;

        // Check again that right tooltip doesn't go out of bounds
        void tooltip2.offsetWidth;
        const updatedRect2 = tooltip2.getBoundingClientRect();

        if (updatedRect2.right > (viewportWidth - rightEdgeMargin)) {
            const secondaryRightOverflow = updatedRect2.right - (viewportWidth - rightEdgeMargin);
            // Adjust both tooltips to compensate
            const currentLeftShift = parseFloat(tooltip2.style.transform.match(/translateX\(([^)]+)\)/)[1]);
            tooltip2.style.transform = `translateX(${currentLeftShift - secondaryRightOverflow}px)`;
            tooltip1.style.transform = `translateX(-${(overlap / 2) + secondaryRightOverflow}px)`;
        }
    }
}



function handleTooltipClick(e, tooltip, index, slider, calendars, firstEntryDate, lastEntryDate, entriesByDate, onChange, tooltips, history) {
    e.stopImmediatePropagation();
    e.preventDefault();

    // Close any currently open calendars first
    closeAllCalendars(calendars, tooltips);

    if (tooltip.classList.contains("calendar-open")) return;
    tooltip.classList.add("calendar-open");

    const currentSliderValue = slider.noUiSlider.get()[index];
    const currentDate = new Date(+currentSliderValue);

    // Find the exact entry that matches the current slider value
    const exactEntry = history.find(entry =>
        new Date(entry.timestamp).getTime() === +currentSliderValue
    );

    // If we have an exact match, use that date, otherwise use the closest date
    const fp = createFlatpickrInstance(tooltip, currentDate, firstEntryDate, lastEntryDate, entriesByDate, index, slider, onChange, calendars, tooltips, history);

    calendars[index] = fp;
    fp.jumpToDate(currentDate);

    // Create and show time selection for the current date immediately
    const dateStr = formatDate(currentDate);
    if (entriesByDate[dateStr] && entriesByDate[dateStr].length > 1) {
        showTimeSelectionForDate(dateStr, entriesByDate, fp, index, currentSliderValue, slider, onChange, tooltips, tooltip, calendars);
    }

    setupCalendarCloseHandler(fp, tooltip, index, calendars, tooltips);
}

// Add this new helper function to close all open calendars
function closeAllCalendars(calendars, tooltips) {
    calendars.forEach((calendar, i) => {
        if (calendar) {
            const tooltip = tooltips[i];
            closeAndCleanupCalendar(calendar, tooltip, i, calendars, tooltips);
        }
    });
}
function createFlatpickrInstance(
    tooltip, currentDate, firstEntryDate, lastEntryDate,
    entriesByDate, index, slider, onChange, calendars, tooltips, history
) {
    const validDates = Object.keys(entriesByDate);
    const startYear = firstEntryDate.getFullYear();
    const endYear = lastEntryDate.getFullYear();

    const otherHandleIndex = index === 0 ? 1 : 0;
    const otherHandleValue = Number(slider.noUiSlider.get()[otherHandleIndex]);
    const otherHandleDate = new Date(otherHandleValue);

    let effectiveMinDate = firstEntryDate;
    let effectiveMaxDate = lastEntryDate;

    if (index === 0) {
        effectiveMaxDate = otherHandleDate;
    } else {
        effectiveMinDate = otherHandleDate;
    }

    const fp = flatpickr(tooltip, {
        defaultDate: currentDate,
        minDate: effectiveMinDate,
        maxDate: effectiveMaxDate,
        inline: true,
        clickOpens: false,
        dateFormat: "Y-m-d",
        disable: [
            date => {
                const dateStr = formatDate(date);
                if (!validDates.includes(dateStr)) return true;

                const entries = entriesByDate[dateStr];
                if (!entries || entries.length === 0) return true;

                return !entries.some(entry => {
                    const entryTime = new Date(entry.timestamp).getTime();
                    return index === 0
                        ? entryTime < otherHandleValue
                        : entryTime > otherHandleValue;
                });
            }
        ],
        monthSelectorType: "dropdown",
        onDayCreate: (dObj, dStr, fpInstance, dayElem) => {
            const dateStr = formatDate(dayElem.dateObj);
            if (validDates.includes(dateStr)) {
                const entries = entriesByDate[dateStr];
                const hasValidEntries = entries && entries.some(entry => {
                    const entryTime = new Date(entry.timestamp).getTime();
                    return index === 0
                        ? entryTime < otherHandleValue
                        : entryTime > otherHandleValue;
                });

                if (hasValidEntries) {
                    dayElem.classList.add("valid-entry-day");

                    const validEntries = entries.filter(entry => {
                        const entryTime = new Date(entry.timestamp).getTime();
                        return index === 0
                            ? entryTime < otherHandleValue
                            : entryTime > otherHandleValue;
                    });

                    if (validEntries.length > 1) {
                        const marker = document.createElement("span");
                        marker.classList.add("calendar-marker");
                        dayElem.appendChild(marker);
                        dayElem.classList.add("relative-day");
                    }
                }
            }
        },
        onChange: selectedDates =>
            handleCalendarDateChange(
                selectedDates, entriesByDate, index,
                slider, onChange, tooltip, calendars, tooltips, history
            ),
        onReady: (_, __, instance) => {
            positionCalendarContainer(instance);
            addCalendarTimeSelectionSupport(instance);
            convertYearNavigationToDropdown(instance, startYear, endYear, index, otherHandleDate);

            setTimeout(() => {
                const yearDropdown = instance.calendarContainer.querySelector('.flatpickr-yearDropdown');
                const monthDropdown = instance.calendarContainer.querySelector('.flatpickr-monthDropdown-months');

                if (yearDropdown) yearDropdown.value = currentDate.getFullYear();
                if (monthDropdown) monthDropdown.value = currentDate.getMonth();
            }, 10);
        }
    });

    return fp;
}


function convertYearNavigationToDropdown(instance, startYear, endYear, index, otherHandleDate) {
    setTimeout(() => {
        const calendarContainer = instance.calendarContainer;
        const currentYearElement = calendarContainer.querySelector('.cur-year');
        const monthDropdown = calendarContainer.querySelector('.flatpickr-monthDropdown-months');

        const yearParent = currentYearElement?.parentNode;
        const yearArrows = yearParent?.querySelectorAll('.arrowUp, .arrowDown');
        yearArrows?.forEach(arrow => arrow.remove());

        if (!currentYearElement || !monthDropdown) return;

        const currentYear = parseInt(currentYearElement.textContent);
        const yearSelect = document.createElement('select');
        yearSelect.className = 'flatpickr-yearDropdown';

        // CSS-Klassen werden genutzt statt Inline-Styles
        monthDropdown.classList.add('flatpickr-monthDropdown-enhanced');

        // Determine valid years based on the other handle
        let effectiveStartYear = startYear;
        let effectiveEndYear = endYear;

        if (otherHandleDate) {
            const otherHandleYear = otherHandleDate.getFullYear();
            if (index === 0) { // Left handle - must be <= otherHandleYear
                effectiveEndYear = Math.min(endYear, otherHandleYear);
            } else { // Right handle - must be >= otherHandleYear
                effectiveStartYear = Math.max(startYear, otherHandleYear);
            }
        }

        for (let year = effectiveStartYear; year <= effectiveEndYear; year++) {
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
            if (instance.currentMonth !== currentMonth) {
                instance.changeMonth(currentMonth, false);
            }
        });

        yearParent.replaceChild(yearSelect, currentYearElement);
    }, 0);
}




function addCalendarTimeSelectionSupport(instance) {
    const timeSelectionContainer = document.createElement("div");
    timeSelectionContainer.className = "flatpickr-time-selection";
    timeSelectionContainer.classList.add("flatpickr-time-selection-enhanced");

    instance.calendarContainer.appendChild(timeSelectionContainer);
    instance._timeSelectionContainer = timeSelectionContainer;
}







function applyExactTimestamp(exactEntry, index, slider, onChange) {
    const exactTimestamp = new Date(exactEntry.timestamp).getTime();
    console.log("Found matching entry with timestamp:", new Date(exactTimestamp).toISOString());

    slider.noUiSlider.setHandle(index, exactTimestamp);
    onChange();
}

function handleInvalidDate(selectedDate, index, slider, onChange, history) {
    console.log("No matching entry found for date:", formatDate(selectedDate));

    const selectedTime = selectedDate.getTime();
    const sortedHistory = [...history].sort((a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    let nearestEntry;

    if (index === 0) { // Left handle - snap to next higher timestamp
        nearestEntry = sortedHistory.find(entry =>
            new Date(entry.timestamp).getTime() >= selectedTime
        );

        // If no higher timestamp found, use the highest available
        if (!nearestEntry) {
            nearestEntry = sortedHistory[sortedHistory.length - 1];
        }
    } else { // Right handle - snap to next lower timestamp
        // Find entries with timestamps less than or equal to the selected time
        const lowerEntries = sortedHistory.filter(entry =>
            new Date(entry.timestamp).getTime() <= selectedTime
        );

        // Get the highest of these lower entries
        nearestEntry = lowerEntries.length > 0
            ? lowerEntries[lowerEntries.length - 1]
            : sortedHistory[0]; // If no lower entry, use the earliest
    }

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



function positionCalendarContainer(instance) {
    const calendar = instance.calendarContainer;
    calendar.classList.add("small-flatpickr");

    // Additional styles for dropdown containers
    const monthContainer = calendar.querySelector('.flatpickr-month');
    if (monthContainer) {
        monthContainer.classList.add('flatpickr-month-container');
    }

    // Style the month dropdown to fit well
    const monthDropdown = calendar.querySelector('.flatpickr-monthDropdown-months');
    if (monthDropdown) {
        monthDropdown.classList.add('flatpickr-month-dropdown');
    }

    // Style the month navigation arrows
    const prevNextButtons = calendar.querySelectorAll('.flatpickr-prev-month, .flatpickr-next-month');
    prevNextButtons.forEach(button => {
        button.classList.add('flatpickr-month-nav-button');
    });

    setTimeout(() => {
        const rect = calendar.getBoundingClientRect();
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

        if (rect.right > viewportWidth) {
            const overflow = rect.right - viewportWidth + 80;
            calendar.style.left = `${calendar.offsetLeft - overflow}px`;
        }
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

