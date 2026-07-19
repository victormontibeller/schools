(function () {
    "use strict";

    if (!("serviceWorker" in navigator)) { return; }
    var hadController = Boolean(navigator.serviceWorker.controller);
    var refreshing = false;
    navigator.serviceWorker.addEventListener("controllerchange", function () {
        if (hadController && !refreshing) {
            refreshing = true;
            window.location.reload();
        }
    });
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/service-worker.js");
    });
}());
