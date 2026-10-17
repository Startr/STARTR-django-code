// The split: a list on the left, the open item on the right; on a phone the
// item slides over the list. startr-swap does the fetching (a row is a swap
// link into #split-pane, Back is a swap of main) and the server renders the
// state (data-on on the split, aria-current on the open row). This script only
// restores that state after a sub-swap, which replaces the pane's children and
// nothing else: data-on, the current row, the title, focus. Looks live in the
// template's inline props; the slide is the kit's --t-in-on. Without the
// script every row is a plain link to the item's page.
(() => {
  "use strict";
  const sync = (split, url) => {
    const pane = split.querySelector("[data-split-pane]");
    const open = pane && pane.querySelector("[data-pane]");
    split.toggleAttribute("data-on", Boolean(open));
    const here = new URL(url || location.href, location.href).href;
    split.querySelectorAll("[data-split-row]").forEach((a) => {
      if (a.href === here) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    const title = open && open.querySelector("[data-pane-title]");
    if (!title) return;
    const name = title.textContent.trim();
    const parts = document.title.split(" — ");
    document.title = parts.length > 1 ? `${name} — ${parts[parts.length - 1]}` : name;
    title.focus();
  };
  document.addEventListener("swap:after", (event) => {
    const pane = event.target;
    if (!(pane instanceof Element) || !pane.matches("[data-split-pane]")) return;
    const split = pane.closest("[data-split]");
    if (split) sync(split, event.detail && event.detail.url);
  });
})();
