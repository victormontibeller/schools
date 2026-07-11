(function () {
    "use strict";

    var navigation = document.querySelector(".landing-nav");
    var revealElements = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var revealObserver = null;
    var scrollFrame = null;

    function updateNavigation() {
        if (!navigation) {
            return;
        }
        navigation.classList.toggle("is-scrolled", window.scrollY > 18);
        scrollFrame = null;
    }

    function requestNavigationUpdate() {
        if (scrollFrame === null) {
            scrollFrame = window.requestAnimationFrame(updateNavigation);
        }
    }

    function showAllRevealElements() {
        revealElements.forEach(function (element) {
            element.classList.add("is-visible");
        });
    }

    function configureReveal() {
        if (reduceMotion.matches || !("IntersectionObserver" in window)) {
            showAllRevealElements();
            return;
        }

        document.documentElement.classList.add("landing-motion");

        revealElements.forEach(function (element) {
            var delay = Math.min(Math.max(Number(element.dataset.revealDelay) || 0, 0), 600);
            element.style.setProperty("--reveal-delay", delay + "ms");
        });

        revealObserver = new window.IntersectionObserver(
            function (entries, observer) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                });
            },
            {
                threshold: 0.12,
                rootMargin: "0px 0px -40px",
            },
        );

        revealElements.forEach(function (element) {
            if (element.dataset.reveal === "hero") {
                window.requestAnimationFrame(function () {
                    element.classList.add("is-visible");
                });
                return;
            }
            revealObserver.observe(element);
        });
    }

    function closeMobileNavigation(event) {
        var link = event.target.closest('a[href^="#"]');
        var menu = document.getElementById("public-navigation");

        if (!link || !menu || !menu.classList.contains("show") || !window.bootstrap) {
            return;
        }

        window.bootstrap.Collapse.getOrCreateInstance(menu, { toggle: false }).hide();
    }

    updateNavigation();
    configureReveal();

    window.addEventListener("scroll", requestNavigationUpdate, { passive: true });
    document.addEventListener("click", closeMobileNavigation);

    function handleReducedMotionChange(event) {
        if (!event.matches) {
            return;
        }
        if (revealObserver) {
            revealObserver.disconnect();
        }
        document.documentElement.classList.remove("landing-motion");
        showAllRevealElements();
    }

    if (typeof reduceMotion.addEventListener === "function") {
        reduceMotion.addEventListener("change", handleReducedMotionChange);
    } else if (typeof reduceMotion.addListener === "function") {
        reduceMotion.addListener(handleReducedMotionChange);
    }
})();
