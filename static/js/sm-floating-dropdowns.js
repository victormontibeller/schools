(function () {
    "use strict";

    function restoreMenu(dropdown) {
        var placeholder = dropdown && dropdown._smFloatingPlaceholder;
        var menu = dropdown && dropdown._smFloatingMenu;
        if (placeholder && placeholder.parentNode && menu) {
            placeholder.parentNode.replaceChild(menu, placeholder);
        }
        if (menu) {
            menu._smFloatingOwner = null;
        }
        if (dropdown) {
            dropdown._smFloatingPlaceholder = null;
            dropdown._smFloatingMenu = null;
        }
    }

    function initialize(root) {
        if (!window.bootstrap || !window.bootstrap.Dropdown) {
            return;
        }
        (root || document)
            .querySelectorAll("[data-sm-floating-dropdown] [data-bs-toggle='dropdown']")
            .forEach(function (toggle) {
                if (toggle.dataset.smFloatingInitialized) {
                    return;
                }
                toggle.dataset.smFloatingInitialized = "true";
                var existing = window.bootstrap.Dropdown.getInstance(toggle);
                if (existing) {
                    existing.dispose();
                }
                new window.bootstrap.Dropdown(toggle, {
                    boundary: "viewport",
                    popperConfig: function (defaultConfig) {
                        var modifiers = (defaultConfig.modifiers || []).filter(
                            function (modifier) {
                                return (
                                    modifier.name !== "flip" &&
                                    modifier.name !== "preventOverflow"
                                );
                            }
                        );
                        modifiers.push(
                            {
                                name: "flip",
                                options: {
                                    fallbackPlacements: ["top", "bottom", "right", "left"],
                                },
                            },
                            {
                                name: "preventOverflow",
                                options: {boundary: "viewport", padding: 8},
                            }
                        );
                        return Object.assign({}, defaultConfig, {
                            strategy: "fixed",
                            modifiers: modifiers,
                        });
                    },
                });
            });
    }

    function owner(element) {
        var dropdown = element && element.closest("[data-sm-floating-dropdown]");
        var menu = element && element.closest("[data-sm-floating-menu]");
        return dropdown || (menu && menu._smFloatingOwner) || null;
    }

    function focusableControls(menu) {
        return Array.prototype.slice.call(
            menu.querySelectorAll(
                "a[href], button:not([disabled]), input:not([disabled]), " +
                    "select:not([disabled]), textarea:not([disabled]), " +
                    "[tabindex]:not([tabindex='-1'])"
            )
        ).filter(function (control) {
            return control.getClientRects().length > 0;
        });
    }

    function focusableControlsOutsideMenus() {
        return Array.prototype.slice.call(
            document.querySelectorAll(
                "a[href], button:not([disabled]), input:not([disabled]), " +
                    "select:not([disabled]), textarea:not([disabled]), " +
                    "[tabindex]:not([tabindex='-1'])"
            )
        ).filter(function (control) {
            return (
                !control.closest("[data-sm-floating-menu]") &&
                control.getClientRects().length > 0
            );
        });
    }

    if (window.SmFloatingDropdowns) {
        window.SmFloatingDropdowns.initialize(document);
        return;
    }

    window.SmFloatingDropdowns = {initialize: initialize, owner: owner};

    document.addEventListener("show.bs.dropdown", function (event) {
        var dropdown = event.target.closest("[data-sm-floating-dropdown]");
        var menu = dropdown && dropdown.querySelector("[data-sm-floating-menu]");
        if (!dropdown || !menu || dropdown._smFloatingPlaceholder) {
            return;
        }
        var placeholder = document.createComment("sm-floating-dropdown-menu");
        menu.parentNode.insertBefore(placeholder, menu);
        dropdown._smFloatingPlaceholder = placeholder;
        dropdown._smFloatingMenu = menu;
        menu._smFloatingOwner = dropdown;
        document.body.appendChild(menu);
    });

    document.addEventListener("shown.bs.dropdown", function (event) {
        var dropdown = event.target.closest("[data-sm-floating-dropdown]");
        var menu = dropdown && dropdown._smFloatingMenu;
        var controls = menu && focusableControls(menu);
        if (controls && controls.length) {
            controls[0].focus();
        }
    });

    document.addEventListener("hidden.bs.dropdown", function (event) {
        var dropdown = event.target.closest("[data-sm-floating-dropdown]");
        var menu = dropdown && dropdown._smFloatingMenu;
        var toggle = dropdown && dropdown.querySelector("[data-bs-toggle='dropdown']");
        var restoreFocus = menu && menu.contains(document.activeElement);
        restoreMenu(dropdown);
        if (restoreFocus && toggle) {
            toggle.focus();
        }
    });

    document.addEventListener("keydown", function (event) {
        var menu = event.target.closest("[data-sm-floating-menu]");
        if (!menu) {
            return;
        }
        var dropdown = menu._smFloatingOwner;
        var toggle = dropdown && dropdown.querySelector("[data-bs-toggle='dropdown']");
        var instance = toggle && window.bootstrap.Dropdown.getOrCreateInstance(toggle);
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            if (instance) {
                instance.hide();
            }
            return;
        }
        if (event.key !== "Tab") {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (instance) {
            instance.hide();
        }
        if (event.shiftKey) {
            if (toggle) {
                toggle.focus();
            }
            return;
        }
        var controls = focusableControlsOutsideMenus();
        var toggleIndex = controls.indexOf(toggle);
        if (toggleIndex >= 0 && controls[toggleIndex + 1]) {
            controls[toggleIndex + 1].focus();
        }
    }, true);

    document.addEventListener("htmx:beforeSwap", function () {
        document
            .querySelectorAll(
                "[data-sm-floating-dropdown] [data-bs-toggle='dropdown'][aria-expanded='true']"
            )
            .forEach(function (toggle) {
                var instance = window.bootstrap && window.bootstrap.Dropdown.getInstance(toggle);
                if (instance) {
                    instance.hide();
                }
            });
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
