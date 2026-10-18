// The dock's behaviour. The bar is one SVG path with a cavity under the
// current page; a bubble sits in the cavity and glides to the next page. This
// script owns geometry and attributes only: the path's d, the bubble's
// position, aria-current, and whether More is open. Every look lives in the
// template's inline props. Without this script the dock is a plain bar and the
// server has already marked the current page.
(() => {
  "use strict";
  const dock = document.querySelector("[data-dock]");
  if (!dock) return;
  const shape = dock.querySelector("[data-dock-shape]");
  const path = shape.querySelector("path");
  const bubble = dock.querySelector("[data-dock-bubble]");
  const glyph = bubble.querySelector("svg");
  const more = dock.querySelector("[data-dock-more]");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");

  const H = 76; // bar height, px
  const r = 20; // corner radius
  const R = 37; // cavity radius: the bubble's 28 plus a 9 px gap
  const s = 16; // the rounded shoulder into the cavity
  const DURATION = 520;
  const ease = (t) => 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2; // ease-out with a slight overshoot

  let cx = null; // the cavity's centre, or null for a plain bar
  let raf = 0;

  const bar = (W) => `M${r} 0H${W - r}Q${W} 0 ${W} ${r}V${H - r}Q${W} ${H} ${W - r} ${H}H${r}Q0 ${H} 0 ${H - r}V${r}Q0 0 ${r} 0Z`;
  // Near either end of the bar (a phone's first item centres about 45px in)
  // the cavity and a full corner do not both fit: the shoulder would start
  // inside the corner's curve and the outline would fold back on itself. So
  // the top corner on that side gives way, its radius shrinking to the room
  // left, down to square, and grows back as the cavity moves off.
  const barWithCavity = (W, x) => {
    x = Math.min(Math.max(x, R + 4), W - R - 4);
    const rl = Math.min(r, Math.max(0, x - R - s));
    const rr = Math.min(r, Math.max(0, W - x - R - s));
    const left = Math.max(x - R - s, rl);
    const right = Math.min(x + R + s, W - rr);
    return (
      `M${rl} 0L${left} 0Q${x - R} 0 ${x - R + 4} 10A${R} ${R} 0 0 0 ${x + R - 4} 10Q${x + R} 0 ${right} 0` +
      `L${W - rr} 0Q${W} 0 ${W} ${rr}V${H - r}Q${W} ${H} ${W - r} ${H}H${r}Q0 ${H} 0 ${H - r}V${rl}Q0 0 ${rl} 0Z`
    );
  };

  const draw = (x) => {
    const W = dock.clientWidth;
    shape.setAttribute("viewBox", `0 0 ${W} ${H}`);
    path.setAttribute("d", x == null ? bar(W) : barWithCavity(W, x));
    if (x == null) {
      bubble.style.setProperty("--d", "none");
      return;
    }
    bubble.style.setProperty("--d", "flex");
    bubble.style.setProperty("--t", `translateX(${(x - bubble.offsetWidth / 2).toFixed(1)}px)`);
  };

  // Dock links the viewer can see at this width (the phone hides most of them).
  const shown = () => [...dock.querySelectorAll("[data-dock-items] > a")].filter((a) => a.getClientRects().length);
  const centreOf = (a) => {
    const b = a.getBoundingClientRect();
    const d = dock.getBoundingClientRect();
    return b.left - d.left + b.width / 2;
  };

  const moveTo = (x, animate) => {
    cancelAnimationFrame(raf);
    if (!animate || reduce.matches || cx == null || x == null) {
      cx = x;
      draw(x);
      return;
    }
    const from = cx;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / DURATION);
      cx = from + (x - from) * ease(t);
      draw(cx);
      if (t < 1) raf = requestAnimationFrame(step);
      else {
        cx = x;
        draw(x);
      }
    };
    raf = requestAnimationFrame(step);
  };

  // Mark every link whose URL is the longest prefix of the path, as the server
  // does. A primary page sits in the dock and in the sheet, one copy shown per
  // width; both copies carry the mark, so the visible one always has it.
  const mark = (pathname) => {
    const links = [...dock.querySelectorAll("a[href]")]
      .map((a) => ({ a, path: new URL(a.getAttribute("href"), location.href) }))
      .filter(({ path }) => path.origin === location.origin);
    let best = "";
    for (const { path } of links) {
      if (pathname.startsWith(path.pathname) && path.pathname.length > best.length) best = path.pathname;
    }
    for (const { a, path } of links) {
      if (best && path.pathname === best) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
  };

  // More stands in for a current page that lives in its sheet: it takes the
  // page's icon in the bubble and its name as the label, and data-on marks
  // it the way aria-current marks a link. Otherwise it is plain "More".
  const summary = more && more.querySelector("summary");
  const label = summary && summary.querySelector("[data-label]");
  const standIn = (link) => {
    if (!summary) return;
    if (link) {
      summary.setAttribute("data-on", "");
      if (label) label.textContent = link.textContent.trim();
    } else {
      summary.removeAttribute("data-on");
      if (label) label.textContent = label.getAttribute("data-label");
    }
  };

  // Put the cavity and bubble under the current shown link; when the current
  // page is in the sheet, under More; when nothing is current, draw a plain bar.
  const settle = (animate) => {
    const inDock = shown().find((link) => link.getAttribute("aria-current") === "page");
    const inSheet = !inDock && more ? more.querySelector("a[aria-current='page']") : null;
    standIn(inSheet);
    const target = inDock || (inSheet && summary && summary.getClientRects().length ? summary : null);
    if (!target) {
      moveTo(null, false);
      return;
    }
    const icon = (inDock || inSheet).querySelector("svg");
    if (icon) glyph.innerHTML = icon.innerHTML;
    moveTo(centreOf(target), animate);
  };

  // A dock click: mark and glide at once, before the swap lands. The swap
  // script's document listener has already run and called preventDefault,
  // so that flag is not a reason to stop; a modifier key is (a new tab). A
  // page outside the swap scope reloads, and the server marks it then.
  dock.addEventListener("click", (event) => {
    const a = event.target.closest("a[href]");
    if (!a || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(a.getAttribute("href"), location.href);
    if (url.origin !== location.origin) return;
    if (more && more.contains(a)) more.removeAttribute("open");
    mark(url.pathname);
    settle(true);
  });

  // After a swap or a history move, the address is the truth. swap:after
  // carries the URL that landed, in case the history entry is written later.
  // A swap keeps the header, so nothing resets focus: move it into <main>, as a
  // full load would, so a keyboard or screen-reader user lands on the new page.
  const main = document.querySelector("main");
  const follow = (event) => {
    const url = event && event.detail && event.detail.url ? new URL(event.detail.url, location.href) : location;
    mark(url.pathname);
    settle(true);
    if (event && event.type === "swap:after" && main) {
      main.setAttribute("tabindex", "-1");
      main.focus({ preventScroll: true });
    }
  };
  document.addEventListener("swap:after", follow);
  addEventListener("popstate", () => follow());

  // More closes on Escape and on a click or tap outside it.
  if (more) {
    addEventListener("keydown", (event) => {
      if (event.key === "Escape" && more.open) {
        more.removeAttribute("open");
        more.querySelector("summary")?.focus();
      }
    });
    addEventListener("pointerdown", (event) => {
      if (more.open && !more.contains(event.target)) more.removeAttribute("open");
    });
  }

  let resizeFrame = 0;
  addEventListener("resize", () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => settle(false));
  });
  reduce.addEventListener?.("change", () => settle(false));

  settle(false);
  document.fonts?.ready.then(() => settle(false));
})();
