// Progressive enhancement only. Every page is complete without this file:
// search forms submit to /search/, filter forms have an Apply button, the
// FAQ is plain HTML. This adds the theme toggle, search suggestions,
// auto-submitting filters and the "on this page" highlight.
(() => {
  const root = document.documentElement;

  // Theme toggle ------------------------------------------------------------
  const toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
      const current = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("ep-theme", next); } catch (e) { /* private mode */ }
    });
  }

  // Search suggestions: an ARIA combobox over /api/v1/search/ -----------------
  let uid = 0;
  document.querySelectorAll("form[data-search]").forEach((form) => {
    const input = form.querySelector("input[name=q]");
    if (!input) return;
    const list = document.createElement("div");
    list.className = "suggest";
    list.id = `suggest-${++uid}`;
    list.setAttribute("role", "listbox");
    list.hidden = true;
    form.append(list);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-expanded", "false");

    let timer, controller, active = -1;
    const items = () => [...list.querySelectorAll("a")];
    const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; };
    const select = (i) => {
      const all = items();
      all.forEach((a, n) => a.setAttribute("aria-selected", String(n === i)));
      active = i;
      if (all[i]) input.setAttribute("aria-activedescendant", all[i].id);
    };
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) return close();
      timer = setTimeout(async () => {
        controller?.abort();
        controller = new AbortController();
        try {
          const res = await fetch(`/api/v1/search/?q=${encodeURIComponent(q)}`, { signal: controller.signal });
          if (!res.ok) return close();
          const { data } = await res.json();
          if (!data.results.length) return close();
          list.innerHTML = data.results.map((r, i) =>
            `<a id="${list.id}-${i}" role="option" aria-selected="false" href="/stocks/${encodeURIComponent(r.ticker.toLowerCase())}/">` +
            `<span class="tkr">${esc(r.ticker)}</span><span>${esc(r.display_name)}</span>` +
            `<span class="suggest__meta">${r.exchange ? esc(r.exchange.name) : ""}</span></a>`).join("");
          list.hidden = false;
          input.setAttribute("aria-expanded", "true");
          active = -1;
        } catch (e) { /* aborted or offline: the form still submits */ }
      }, 150);
    });

    input.addEventListener("keydown", (e) => {
      const all = items();
      if (list.hidden || !all.length) return;
      if (e.key === "ArrowDown") { e.preventDefault(); select((active + 1) % all.length); }
      else if (e.key === "ArrowUp") { e.preventDefault(); select((active - 1 + all.length) % all.length); }
      else if (e.key === "Enter" && active >= 0) { e.preventDefault(); location.href = all[active].href; }
      else if (e.key === "Escape") close();
    });
    document.addEventListener("click", (e) => { if (!form.contains(e.target)) close(); });
  });

  // Directory filters submit on change; the Apply button stays for no-JS -----
  document.querySelectorAll("form[data-autosubmit]").forEach((form) => {
    form.addEventListener("change", (e) => { if (e.target.matches("select")) form.requestSubmit(); });
  });

  // "On this page": mark the section being read ---------------------------------
  const links = [...document.querySelectorAll(".toc a[href^='#']")];
  if (links.length && "IntersectionObserver" in window) {
    const byId = new Map(links.map((a) => [a.hash.slice(1), a]));
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((a) => a.removeAttribute("aria-current"));
        byId.get(entry.target.id)?.setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-15% 0px -75% 0px" });
    byId.forEach((_, id) => { const el = document.getElementById(id); if (el) observer.observe(el); });
  }
})();
