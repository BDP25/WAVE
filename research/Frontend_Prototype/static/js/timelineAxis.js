

export function appendTimelineAxis(sliderWrapper, startDate, endDate) {
    const timelineAxis = createTimelineAxis(startDate, endDate);
    sliderWrapper.appendChild(timelineAxis);
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
