document.addEventListener("DOMContentLoaded", function() {
    // ...existing code...
    var headings = document.querySelectorAll('.mw-parser-output h2, .mw-parser-output h3');
    headings.forEach(function(heading) {
        var sibling = heading.previousElementSibling;
        while (sibling) {
            var comp = window.getComputedStyle(sibling);
            if ((sibling.tagName === "FIGURE" || sibling.tagName === "IMG") && comp.float === "right") {
                // Include sibling's margin-right into the extraPadding calculation
                var siblingMarginRight = parseFloat(comp.marginRight) || 0;
                var extraPadding = sibling.offsetWidth + siblingMarginRight + 10; // 10px gap
                var currentPadding = parseFloat(window.getComputedStyle(heading).paddingRight) || 0;
                if (extraPadding > currentPadding) {
                    heading.style.paddingRight = extraPadding + "px";
                }
                break;
            }
            sibling = sibling.previousElementSibling;
        }
    });
    // ...existing code...
});
