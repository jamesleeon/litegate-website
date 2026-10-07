// Progressive enhancement only: every section is readable without this script.
document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
    const LANGUAGE_STORAGE_KEY = "litegate-preferred-language";

    // Language switching is manual: remember the choice, never auto-redirect
    // on load (avoids redirect flashes and loops).
    document.querySelectorAll("[data-lang-switch]").forEach((anchor) => {
        anchor.addEventListener("click", () => {
            try {
                window.localStorage.setItem(LANGUAGE_STORAGE_KEY, anchor.dataset.langSwitch);
            } catch (error) {
                // Storage can be unavailable (private mode); the link still works.
            }
        });
    });

    const nav = document.querySelector(".nav");
    if (nav) {
        const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
    }

    const toggle = document.querySelector(".nav-toggle");
    const links = document.querySelector(".nav-links");
    if (toggle && links) {
        toggle.addEventListener("click", () => {
            const open = links.classList.toggle("open");
            toggle.setAttribute("aria-expanded", String(open));
        });
        links.addEventListener("click", (event) => {
            if (event.target.closest("a")) {
                links.classList.remove("open");
                toggle.setAttribute("aria-expanded", "false");
            }
        });
    }

    // Tabs: buttons with aria-controls toggle sibling panels inside [data-tabs].
    document.querySelectorAll("[data-tabs]").forEach((group) => {
        const tabs = Array.from(group.querySelectorAll('[role="tab"]'));
        const select = (tab) => {
            tabs.forEach((other) => {
                const selected = other === tab;
                other.setAttribute("aria-selected", String(selected));
                other.tabIndex = selected ? 0 : -1;
                const panel = document.getElementById(other.getAttribute("aria-controls"));
                if (panel) {
                    panel.hidden = !selected;
                }
            });
        };
        tabs.forEach((tab, index) => {
            tab.addEventListener("click", () => select(tab));
            tab.addEventListener("keydown", (event) => {
                const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                if (step) {
                    const next = tabs[(index + step + tabs.length) % tabs.length];
                    select(next);
                    next.focus();
                }
            });
        });
    });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
        document.querySelectorAll("[data-animate]").forEach((element) => observer.observe(element));
    } else {
        document.querySelectorAll("[data-animate]").forEach((element) => element.classList.add("visible"));
    }
});
