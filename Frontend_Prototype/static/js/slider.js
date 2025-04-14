
export function createDateSliderWithPicker(container, history) {
    container.innerHTML = "";

    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "slider-wrapper";

    const slider = document.createElement("div");
    slider.id = "multi-range-slider";
    sliderWrapper.appendChild(slider);

    const years = history.map(entry => new Date(entry.timestamp).getFullYear());
    const minYear = Math.min(...years);
    const maxYear = Math.max(...years);

    const sortedHistory = history.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const tenthToLastTimestamp = sortedHistory.length >= 10
        ? new Date(sortedHistory[sortedHistory.length - 10].timestamp)
        : new Date(sortedHistory[0].timestamp);

    const timelineAxis = createTimelineAxis(minYear, maxYear, history);
    sliderWrapper.appendChild(timelineAxis);
    container.appendChild(sliderWrapper);

    if (slider.noUiSlider) slider.noUiSlider.destroy();

    const sliderRange = minYear === maxYear
        ? { min: 0, max: 11 }
        : { min: minYear, max: maxYear };

    const sliderStart = minYear === maxYear
        ? [new Date(tenthToLastTimestamp).getMonth(), 11]
        : [tenthToLastTimestamp.getFullYear(), maxYear];

    noUiSlider.create(slider, {
        start: sliderStart,
        connect: true,
        range: sliderRange,
        step: 1,
        tooltips: [
            {
                to: value => {
                    if (minYear === maxYear) {
                        const month = Math.floor(value);
                        return `${minYear}-${String(month + 1).padStart(2, "0")}-01`;
                    }
                    return `${Math.round(value)}`;
                },
                from: value => Number(value)
            },
            {
                to: value => {
                    if (minYear === maxYear) {
                        const month = Math.floor(value);
                        return `${minYear}-${String(month + 1).padStart(2, "0")}-01`;
                    }
                    return `${Math.round(value)}`;
                },
                from: value => Number(value)
            }
        ]
    });

    setupSliderTooltips(slider, tenthToLastTimestamp, maxYear, minYear === maxYear);
}

function createTimelineAxis(minYear, maxYear, history) {
    const timelineAxis = document.createElement("div");
    timelineAxis.className = "timeline-axis";

    const yearRange = maxYear - minYear;
    if (yearRange === 0) {
        for (let month = 0; month < 12; month += 2) {
            const label = document.createElement("span");
            label.className = "month-label";
            label.textContent = `${minYear}-${String(month + 1).padStart(2, "0")}`;
            timelineAxis.appendChild(label);
        }
    } else if (yearRange <= 2) {
        for (let year = minYear; year <= maxYear; year++) {
            for (let month = 0; month < 12; month += 3) {
                const label = document.createElement("span");
                label.className = "month-label";
                label.textContent = `${year}-${String(month + 1).padStart(2, "0")}`;
                timelineAxis.appendChild(label);
            }
        }
    } else if (yearRange <= 10) {
        for (let year = minYear; year <= maxYear; year++) {
            const yearLabel = document.createElement("span");
            yearLabel.className = "year-label";
            yearLabel.textContent = year;
            timelineAxis.appendChild(yearLabel);
        }
    } else {
        for (let year = minYear; year <= maxYear; year += 5) {
            const yearLabel = document.createElement("span");
            yearLabel.className = "year-label";
            yearLabel.textContent = year;
            timelineAxis.appendChild(yearLabel);
        }
    }

    return timelineAxis;
}

function setupSliderTooltips(slider, tenthToLastTimestamp, maxYear) {
    const selectedDates = [tenthToLastTimestamp.toISOString().split("T")[0], null];

    setTimeout(() => {
        const tooltips = slider.querySelectorAll(".noUi-tooltip");

        tooltips.forEach((tooltip, index) => {
            tooltip.style.cursor = "pointer";

            tooltip.addEventListener("click", () => {
                const input = document.createElement("input");
                input.type = "date";
                input.className = "date-picker-input";
                input.value = index === 0 ? selectedDates[0] : maxYear;

                const rect = tooltip.getBoundingClientRect();
                input.style.left = `${rect.left}px`;
                input.style.top = `${rect.bottom + window.scrollY}px`;

                document.body.appendChild(input);

                input.addEventListener("change", () => {
                    const selectedDate = new Date(input.value).getFullYear();
                    selectedDates[index] = input.value;
                    tooltip.innerText = input.value;
                    slider.noUiSlider.setHandle(index, selectedDate);
                    input.remove();
                });

                input.addEventListener("input", () => {
                    const selectedDate = new Date(input.value).getFullYear();
                    slider.noUiSlider.setHandle(index, selectedDate);
                });

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
    }, 200);
}