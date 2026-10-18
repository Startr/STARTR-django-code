// The tiers' behaviour. Two indicators follow the current group and page: the
// bar under the group, the pill under the page, each placed by left and width
// from the element it marks. Both sit inside the row that scrolls, so they
// scroll and clip with their links; a row keeps one pill, and the shown row's
// pill is the one in use. Clicking a group reveals its row in place (no
// navigation; the group link still works without this script). After a swap
// or a history move the address decides the current page and its group. On a
// phone a row is wider than the screen, so the current group and page are
// scrolled into view when the page loads, a group is opened or the address
// moves. This script sets attributes (aria-current, hidden), geometry and the
// scroll of its own rows; looks live in the template's inline props, and
// reduced motion is the kit's --tn guard.
(() => {
  "use strict";
  const tiers = document.querySelector("[data-tiers]");
  if (!tiers) return;
  const bar = tiers.querySelector("[data-tiers-bar]");
  const pills = [...tiers.querySelectorAll("[data-tiers-pill]")];
  const groups = [...tiers.querySelectorAll("[data-tiers-groups] a[data-group]")];
  const rows = [...tiers.querySelectorAll("[data-row]")];
  const pages = () => [...tiers.querySelectorAll("[data-row] a[href]")];
  let shown = Math.max(0, groups.findIndex((g) => g.hasAttribute("aria-current")));

  // The indicators carry --left and --w (kit props, !important), so the
  // geometry goes into those props, where a plain left/width would lose. A
  // target and its indicator share one positioned, scrolling parent, so the
  // target's offsetLeft is the indicator's left.
  const fit = (el, target) => {
    el.style.setProperty("--left", `${target.offsetLeft}px`);
    el.style.setProperty("--w", `${target.offsetWidth}px`);
  };

  const placePill = () => {
    const row = rows[shown];
    const pill = row && row.querySelector("[data-tiers-pill]");
    const current = row && row.querySelector("a[aria-current], a[data-on]");
    if (!pill) return;
    pill.style.setProperty("--op", current ? "1" : "0");
    if (current) fit(pill, current);
  };

  // Scroll the row that holds `el` just far enough to show it, and nothing else:
  // scrollIntoView would also drag the page back to the header after a Back with the header off screen.
  // The row's own padding stays beside the item, so the last link does not sit on the edge.
  const reveal = (el) => {
    const scroller = el && el.offsetParent;
    if (!scroller) return;
    const pad = parseFloat(getComputedStyle(scroller).paddingLeft) || 0;
    const left = el.offsetLeft - pad;
    const right = el.offsetLeft + el.offsetWidth + pad;
    if (left < scroller.scrollLeft) scroller.scrollLeft = left;
    else if (right > scroller.scrollLeft + scroller.clientWidth) scroller.scrollLeft = right - scroller.clientWidth;
  };

  // The current group, and in its row the current page and the crumb after it.
  const revealCurrent = () => {
    reveal(groups[shown]);
    const row = rows[shown];
    if (row) row.querySelectorAll("a[aria-current], a[data-on], [data-tiers-tail]").forEach(reveal);
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
    revealCurrent();
  };

  groups.forEach((g, i) =>
    g.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (i !== shown) {
        showGroup(i);
        revealCurrent();
      }
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

  // First paint: place the indicators without a glide from zero. The kit gives a
  // prop-driven transition (`[style*="--tn:"]`) !important, which only an inline
  // !important can beat, so that is how "none" is set; it comes off again after two frames.
  const still = (fn) => {
    const moving = [bar, ...pills];
    moving.forEach((el) => el.style.setProperty("transition", "none", "important"));
    fn();
    requestAnimationFrame(() => requestAnimationFrame(() => moving.forEach((el) => el.style.removeProperty("transition"))));
  };
  const settle = () => still(() => {
    showGroup(shown);
    revealCurrent();
  });
  settle();
  document.fonts?.ready.then(settle);
  let frame = 0;
  addEventListener("resize", () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => still(() => showGroup(shown)));
  });
})();
