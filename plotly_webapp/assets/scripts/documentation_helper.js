(function () {
  function isElementVisible(el) {
    if (!el) return false;

    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") {
      return false;
    }

    let parent = el.parentElement;
    while (parent) {
      const parentStyle = window.getComputedStyle(parent);
      if (
        parentStyle.display === "none" ||
        parentStyle.visibility === "hidden"
      ) {
        return false;
      }
      parent = parent.parentElement;
    }

    return true;
  }

  function updateActiveSection() {
    const headings = Array.from(
      document.querySelectorAll(".component-page__content h2[id]"),
    ).filter(isElementVisible);

    if (!headings.length) return;

    let closest = null;
    let smallestDistance = Infinity;

    headings.forEach((heading) => {
      const rect = heading.getBoundingClientRect();

      // Only consider headings that have passed the top slightly
      if (rect.top <= window.innerHeight * 0.6) {
        const distance = Math.abs(rect.top);
        if (distance < smallestDistance) {
          smallestDistance = distance;
          closest = heading;
        }
      }
    });

    if (!closest) return;

    const id = closest.getAttribute("id");

    const links = document.querySelectorAll(
      ".component-page__table-contents-link",
    );

    links.forEach((link) =>
      link.classList.remove("component-page__table-contents-link--active"),
    );

    const activeLink = document.querySelector(
      `.component-page__table-contents-link[href="#${CSS.escape(id)}"]`,
    );

    if (activeLink) {
      activeLink.classList.add("component-page__table-contents-link--active");
    }
  }

  // Throttled scroll handler (smooth + performant)
  let ticking = false;

  function onScroll() {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        updateActiveSection();
        ticking = false;
      });
      ticking = true;
    }
  }

  function initScrollSpy() {
    updateActiveSection();

    window.addEventListener("scroll", onScroll);
    window.addEventListener("resize", updateActiveSection);

    // If content changes dynamically (tabs, collapsible sections)
    const container =
      document.querySelector(".component-page__content") || document.body;

    const observer = new MutationObserver(() => {
      updateActiveSection();
    });

    observer.observe(container, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initScrollSpy);
  } else {
    initScrollSpy();
  }
})();
