// The tiers' behaviour. Two indicators follow the current group and page: the
// bar under the group, the pill under the page, each placed by left and width
// from the element it marks. Clicking a group reveals its row in place (no
// navigation; the group link still works without this script). After a swap
// or a history move the address decides the current page and its group. This
// script sets attributes (aria-current, hidden) and geometry only; looks live
// in the template's inline props, and reduced motion is the kit's --tn guard.
(() => {
  "use strict";
  const tiers = document.querySelector("[data-tiers]");
  if (!tiers) return;
  const bar = tiers.querySelector("[data-tiers-bar]");
  const pill = tiers.querySelector("[data-tiers-pill]");
  const groups = [...tiers.querySelectorAll("[data-tiers-groups] a[data-group]")];
  const rows = [...tiers.querySelectorAll("[data-row]")];
  const pages = () => [...tiers.querySelectorAll("[data-row] a[href]")];
  let shown = Math.max(0, groups.findIndex((g) => g.hasAttribute("aria-current")));

  // The indicators carry --left and --w (kit props, !important), so the
  // geometry goes into those props, where a plain left/width would lose.
  const fit = (el, target, offset = 0) => {
    el.style.setProperty("--left", `${target.offsetLeft + offset}px`);
    el.style.setProperty("--w", `${target.offsetWidth}px`);
  };

  const placePill = () => {
    const row = rows[shown];
    const current = row && row.querySelector("a[aria-current], a[data-on]");
    pill.style.setProperty("--op", current ? "1" : "0");
    if (current) fit(pill, current, row.firstElementChild ? row.firstElementChild.offsetLeft - row.firstElementChild.scrollLeft : 0);
  };

  const showGroup = (index) => {
    shown = index;
    groups.forEach((g, i) => (i === index ? g.setAttribute("aria-current", "true") : g.removeAttribute("aria-current")));
    rows.forEach((row, i) => (row.hidden = i !== index));
    if (groups[index]) fit(bar, groups[index]);
    placePill();
  };

  // Mark every page link whose URL is the longest prefix of the path, then show its group.
  const follow = (pathname) => {
    const links = pages().map((a) => ({ a, path: new URL(a.getAttribute("href"), location.href).pathname }));
    let best = "";
    for (const { path } of links) if (pathname.startsWith(path) && path.length > best.length) best = path;
    let index = shown;
    for (const { a, path } of links) {
      if (best && path === best) {
        a.setAttribute("aria-current", "page");
        index = rows.findIndex((row) => row.contains(a));
      } else a.removeAttribute("aria-current");
    }
    showGroup(index < 0 ? shown : index);
  };

  groups.forEach((g, i) =>
    g.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (i !== shown) showGroup(i);
    }),
  );
  tiers.addEventListener("click", (event) => {
    const a = event.target.closest("[data-row] a[href]");
    if (!a || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    follow(new URL(a.getAttribute("href"), location.href).pathname);
  });
  document.addEventListener("swap:after", (event) => {
    const url = event.detail && event.detail.url ? new URL(event.detail.url, location.href) : location;
    follow(url.pathname);
  });
  addEventListener("popstate", () => follow(location.pathname));

  // First paint: place both indicators without a glide from zero.
  const still = (fn) => {
    const saved = [bar.style.transition, pill.style.transition];
    bar.style.transition = pill.style.transition = "none";
    fn();
    requestAnimationFrame(() => requestAnimationFrame(() => ([bar.style.transition, pill.style.transition] = saved)));
  };
  still(() => showGroup(shown));
  document.fonts?.ready.then(() => still(() => showGroup(shown)));
  let frame = 0;
  addEventListener("resize", () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => still(() => showGroup(shown)));
  });
})();
