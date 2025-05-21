

export function formatDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function findClosestEntry(history, timestamp) {
    return history.reduce((closest, entry) => {
        const entryTime = new Date(entry.timestamp).getTime();
        const closestTime = new Date(closest.timestamp).getTime();
        return Math.abs(entryTime - timestamp) < Math.abs(closestTime - timestamp) ? entry : closest;
    });
}

export function findClosestTimestamp(timestamps, target) {
    return timestamps.reduce((prev, curr) =>
        Math.abs(curr - target) < Math.abs(prev - target) ? curr : prev
    );
}

export function extractValidTimestamps(sortedHistory) {
    return sortedHistory.map(entry => new Date(entry.timestamp).getTime());
}

export function prepareTooltipData(history) {
    const firstEntryDate = new Date(history[0].timestamp);
    const lastEntryDate = new Date(history[history.length - 1].timestamp);

    const entriesByDate = {};
    history.forEach(entry => {
        const dateStr = formatDate(new Date(entry.timestamp));
        if (!entriesByDate[dateStr]) {
            entriesByDate[dateStr] = [];
        }
        entriesByDate[dateStr].push(entry);
    });

    Object.keys(entriesByDate).forEach(dateStr => {
        entriesByDate[dateStr].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    });

    return { firstEntryDate, lastEntryDate, entriesByDate };
}

export function getKeyEntries(sortedHistory) {
    const firstEntry = sortedHistory[0];
    const lastEntry = sortedHistory[sortedHistory.length - 1];
    const tenthNewestEntry = sortedHistory[Math.max(0, sortedHistory.length - 10)];
    return { firstEntry, lastEntry, tenthNewestEntry };
}

export function calculateTimeRanges(firstEntry, lastEntry, tenthNewestEntry) {
    const fullRangeStart = new Date(firstEntry.timestamp).getTime();
    const fullRangeEnd = new Date(lastEntry.timestamp).getTime();
    const sliderStart = new Date(tenthNewestEntry.timestamp).getTime();
    const sliderEnd = new Date(lastEntry.timestamp).getTime();
    return { fullRangeStart, fullRangeEnd, sliderStart, sliderEnd };
}




export function applyExactTimestamp(exactEntry, index, slider, onChange) {
    const exactTimestamp = new Date(exactEntry.timestamp).getTime();
    console.log("Found matching entry with timestamp:", new Date(exactTimestamp).toISOString());

    slider.noUiSlider.setHandle(index, exactTimestamp);
    onChange();
}

export function handleInvalidDate(selectedDate, index, slider, onChange, history) {
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