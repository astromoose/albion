/* ALBION - Theme toggle & utilities */

(function () {
    const html = document.documentElement;
    const stored = localStorage.getItem("albion-theme");

    // Apply stored preference or let CSS handle OS default
    if (stored) {
        html.setAttribute("data-theme", stored);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const toggle = document.getElementById("theme-toggle");
        if (!toggle) return;

        toggle.addEventListener("click", () => {
            const current = html.getAttribute("data-theme");
            let next;

            if (current === "dark") {
                next = "light";
            } else if (current === "light") {
                next = "dark";
            } else {
                // Auto mode - check OS preference and toggle opposite
                const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
                next = prefersDark ? "light" : "dark";
            }

            html.setAttribute("data-theme", next);
            localStorage.setItem("albion-theme", next);
        });
    });
})();
