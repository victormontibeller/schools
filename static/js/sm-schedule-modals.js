(function (window, document) {
    "use strict";

    var cellState = {pending: null, returnFocus: null, returnFocusId: null, trigger: null};
    var copyState = {pending: null, returnFocus: null, returnFocusId: null, trigger: null};

    function modal(id) {
        return document.getElementById(id);
    }

    function clearPending(state, event) {
        var detail = event && event.detail;
        if (!state.pending) {
            return;
        }
        if (
            (detail && detail.requestConfig === state.pending.requestConfig)
            || (event && event.type === "htmx:abort" && event.target === state.pending.trigger)
        ) {
            state.pending = null;
        }
    }

    function resetModal(element, kind) {
        var prefix = kind === "cell" ? "schedule-cell" : "schedule-copy";
        var title = element.querySelector("#" + prefix + "-modal-title");
        var context = element.querySelector("#" + prefix + "-modal-context");
        var body = element.querySelector("#" + prefix + "-modal-body");
        if (title) {
            title.textContent = kind === "cell" ? "Editar horário" : "Copiar dia";
        }
        if (context) {
            context.textContent = "Carregando formulário.";
        }
        if (body) {
            body.innerHTML = '<p class="mb-0 text-muted">Carregando formulário.</p>';
        }
    }

    function resetState(state) {
        state.pending = null;
        state.returnFocus = null;
        state.returnFocusId = null;
        state.trigger = null;
    }

    function clearBootstrapArtifacts() {
        document.querySelectorAll(".modal-backdrop").forEach(function (backdrop) {
            backdrop.remove();
        });
        document.body.classList.remove("modal-open");
        ["overflow", "padding-right"].forEach(function (property) {
            document.body.style.removeProperty(property);
            document.body.removeAttribute("data-bs-" + property);
        });
    }

    function teardown() {
        resetState(cellState);
        resetState(copyState);
        document.querySelectorAll("#app-modal-root .modal").forEach(function (element) {
            if (element.id === "schedule-cell-modal") {
                resetModal(element, "cell");
            } else if (element.id === "schedule-copy-modal") {
                resetModal(element, "copy");
            }
            if (window.bootstrap && window.bootstrap.Modal) {
                var instance = window.bootstrap.Modal.getInstance(element);
                if (instance) {
                    var fading = element.classList.contains("fade");
                    element.classList.remove("fade");
                    instance.hide();
                    instance.dispose();
                    if (fading) {
                        element.classList.add("fade");
                    }
                }
            }
            element.classList.remove("show");
            element.style.removeProperty("display");
            element.removeAttribute("aria-modal");
            element.setAttribute("aria-hidden", "true");
        });
        clearBootstrapArtifacts();
    }

    function syncPortal(responseDocument) {
        var current = document.getElementById("app-modal-root");
        var incoming = responseDocument.querySelector("#app-modal-root");
        if (!current || !incoming) {
            return false;
        }
        teardown();
        current.replaceWith(document.importNode(incoming, true));
        return true;
    }

    function focusField(element, invalidOnly) {
        var field = element.querySelector(
            "input.is-invalid, select.is-invalid, textarea.is-invalid, "
            + "input[aria-invalid='true'], select[aria-invalid='true'], textarea[aria-invalid='true']"
        );
        if (!field && !invalidOnly) {
            field = Array.from(element.querySelectorAll("input, select, textarea")).find(
                function (candidate) {
                    return candidate.type !== "hidden" && !candidate.disabled
                        && !candidate.readOnly && candidate.getClientRects().length;
                }
            );
        }
        if (field) {
            field.focus();
        }
    }

    function openAfterSwap(event, state, modalId, targetId, selector) {
        var target = event.detail.target;
        if (!target || target.id !== targetId) {
            return;
        }
        var element = modal(modalId);
        if (!state.pending) {
            if (element && element.classList.contains("show")) {
                focusField(element, true);
            }
            return;
        }
        if (event.detail.requestConfig !== state.pending.requestConfig) {
            return;
        }
        var trigger = state.pending.trigger;
        state.pending = null;
        if (!trigger.isConnected || !trigger.matches(selector) || !element
            || !window.bootstrap || !window.bootstrap.Modal) {
            return;
        }
        element.addEventListener("shown.bs.modal", function () {
            focusField(element, false);
        }, {once: true});
        window.bootstrap.Modal.getOrCreateInstance(element).show();
    }

    function restoreFocus(state) {
        var targetId = state.returnFocusId;
        var fallback = state.returnFocus || state.trigger;
        resetState(state);
        function focusTarget() {
            var target = targetId ? document.getElementById(targetId) : fallback;
            if (target && target.isConnected) {
                target.focus({preventScroll: true});
            }
        }
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(focusTarget);
        });
        window.setTimeout(focusTarget, 350);
    }

    document.body.addEventListener("htmx:beforeRequest", function (event) {
        var source = event.detail.elt;
        var state;
        if (source && source.matches("[data-sm-schedule-cell-modal]")) {
            state = cellState;
        } else if (source && source.matches("[data-sm-schedule-copy-modal]")) {
            state = copyState;
        }
        if (state) {
            state.trigger = source;
            state.returnFocus = null;
            state.returnFocusId = null;
            state.pending = {requestConfig: event.detail.requestConfig, trigger: source};
        }
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        openAfterSwap(
            event, copyState, "schedule-copy-modal", "schedule-copy-modal-body",
            "[data-sm-schedule-copy-modal]"
        );
        openAfterSwap(
            event, cellState, "schedule-cell-modal", "schedule-cell-modal-body",
            "[data-sm-schedule-cell-modal]"
        );
    });

    document.body.addEventListener("schedule-cell-saved", function (event) {
        var element = modal("schedule-cell-modal");
        if (!element || !window.bootstrap || !window.bootstrap.Modal) {
            return;
        }
        cellState.returnFocusId = event.detail && event.detail.returnFocus;
        window.bootstrap.Modal.getOrCreateInstance(element).hide();
    });

    document.body.addEventListener("schedule-day-copied", function (event) {
        var element = modal("schedule-copy-modal");
        if (!element || !window.bootstrap || !window.bootstrap.Modal) {
            return;
        }
        copyState.returnFocusId = (event.detail && event.detail.returnFocus)
            || "schedule-copy-day-trigger";
        window.bootstrap.Modal.getOrCreateInstance(element).hide();
    });

    document.addEventListener("hidden.bs.modal", function (event) {
        if (event.target.id === "schedule-cell-modal") {
            resetModal(event.target, "cell");
            restoreFocus(cellState);
        } else if (event.target.id === "schedule-copy-modal") {
            resetModal(event.target, "copy");
            restoreFocus(copyState);
        }
    });

    ["htmx:abort", "htmx:responseError", "htmx:sendError", "htmx:timeout"].forEach(
        function (name) {
            document.body.addEventListener(name, function (event) {
                clearPending(cellState, event);
                clearPending(copyState, event);
            });
        }
    );
    document.body.addEventListener("htmx:afterRequest", function (event) {
        if (event.detail && event.detail.failed) {
            clearPending(cellState, event);
            clearPending(copyState, event);
        }
    });

    window.SmScheduleModals = {syncPortal: syncPortal, teardown: teardown};
}(window, document));
