document.addEventListener("DOMContentLoaded", () => {
    const LANGUAGE_STORAGE_KEY = "litegate-preferred-language";
    const nav = document.getElementById("nav");

    const normalizePathname = (pathname) => {
        if (!pathname || pathname === "/") {
            return "/index.html";
        }

        return pathname.endsWith("/") ? `${pathname}index.html` : pathname;
    };

    const getLocaleFromPathname = (pathname) => {
        return normalizePathname(pathname).includes("/en/") ? "en" : "zh";
    };

    const getBrowserLocale = () => {
        const languages = Array.isArray(window.navigator.languages) && window.navigator.languages.length > 0
            ? window.navigator.languages
            : [window.navigator.language || "zh-CN"];

        return languages.some((language) => String(language).toLowerCase().startsWith("zh")) ? "zh" : "en";
    };

    const getLocalizedPathname = (pathname, targetLocale) => {
        const normalizedPath = normalizePathname(pathname);

        if (targetLocale === "en") {
            if (normalizedPath.includes("/en/")) {
                return normalizedPath;
            }

            const lastSlashIndex = normalizedPath.lastIndexOf("/");
            const basePath = normalizedPath.slice(0, lastSlashIndex);
            const fileName = normalizedPath.slice(lastSlashIndex + 1);
            return `${basePath}/en/${fileName}`.replace(/\/{2,}/g, "/");
        }

        return normalizedPath.replace("/en/", "/");
    };

    const persistLanguageChoice = (locale) => {
        try {
            window.localStorage.setItem(LANGUAGE_STORAGE_KEY, locale);
        } catch (error) {
            // Ignore storage failures and fall back to browser language.
        }
    };

    const resolvePreferredLocale = () => {
        try {
            const storedLocale = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
            if (storedLocale === "zh" || storedLocale === "en") {
                return storedLocale;
            }
        } catch (error) {
            // Ignore storage failures and fall back to browser language.
        }

        return getBrowserLocale();
    };

    const currentPathname = normalizePathname(window.location.pathname);
    const currentLocale = getLocaleFromPathname(currentPathname);
    const preferredLocale = resolvePreferredLocale();

    if (preferredLocale !== currentLocale) {
        const targetPathname = getLocalizedPathname(currentPathname, preferredLocale);

        if (targetPathname !== currentPathname) {
            const nextUrl = `${targetPathname}${window.location.search}${window.location.hash}`;
            window.location.replace(nextUrl);
            return;
        }
    }

    document.querySelectorAll(".nav-lang-switch, [data-lang-switch]").forEach((anchor) => {
        anchor.addEventListener("click", () => {
            const href = anchor.getAttribute("href");
            if (!href) {
                return;
            }

            const targetUrl = new URL(href, window.location.href);
            persistLanguageChoice(getLocaleFromPathname(targetUrl.pathname));
        });
    });

    if (nav) {
        const onScroll = () => {
            if (window.scrollY > 24) {
                nav.classList.add("scrolled");
            } else {
                nav.classList.remove("scrolled");
            }
        };

        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.14,
        rootMargin: "0px 0px -40px 0px"
    });

    document.querySelectorAll("[data-animate]").forEach((element) => {
        observer.observe(element);
    });

    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener("click", (event) => {
            const href = anchor.getAttribute("href");
            if (!href || href === "#") {
                return;
            }

            const target = document.querySelector(href);
            if (!target) {
                return;
            }

            event.preventDefault();
            target.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        });
    });
});
