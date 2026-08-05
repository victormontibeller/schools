(function () {
    "use strict";

    function feedbackFields(root) {
        var scope = root && root.querySelectorAll ? root : document;
        var fields = [];
        if (scope.matches && scope.matches("[data-activity-score-feedback]")) {
            fields.push(scope);
        }
        return fields.concat(
            Array.prototype.slice.call(
                scope.querySelectorAll("[data-activity-score-feedback]")
            )
        );
    }

    function initialize(root) {
        feedbackFields(root).forEach(function (feedback) {
            var enhanced = feedback.querySelector(
                "[data-activity-score-feedback-enhanced]"
            );
            var fallback = feedback.querySelector(
                "[data-activity-score-feedback-fallback]"
            );
            var expandedInput = enhanced && enhanced.querySelector("textarea");
            var fallbackInput = fallback && fallback.querySelector("textarea");
            if (!enhanced || !fallback || !expandedInput || !fallbackInput) {
                return;
            }
            enhanced.hidden = false;
            expandedInput.disabled = false;
            fallback.hidden = true;
            fallbackInput.disabled = true;
            feedback.dataset.activityScoreFeedbackEnhanced = "true";
        });
        if (window.SmFloatingDropdowns) {
            window.SmFloatingDropdowns.initialize(root || document);
        }
    }

    function updateSummary(input) {
        var dropdown = window.SmFloatingDropdowns && window.SmFloatingDropdowns.owner(input);
        var summary = dropdown && dropdown.querySelector(
            "[data-activity-score-feedback-summary]"
        );
        if (summary) {
            summary.textContent = input.value.trim() ? "Com observação" : "Sem observação";
        }
    }

    if (window.SmActivityScoreFeedback) {
        window.SmActivityScoreFeedback.initialize(document);
        return;
    }

    window.SmActivityScoreFeedback = {initialize: initialize};

    document.addEventListener("input", function (event) {
        var input = event.target.closest("[data-activity-score-feedback-input]");
        if (input && !input.disabled) {
            updateSummary(input);
        }
    });
    document.addEventListener("htmx:afterSwap", function (event) {
        initialize(event.target || (event.detail && event.detail.elt));
    });

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            function () {
                initialize(document);
            },
            {once: true}
        );
    } else {
        initialize(document);
    }
})();
