// The user menu's behaviour: a plain <details> that closes on Escape (focus
// back on its button), on a click or tap outside it, and once a link inside is
// followed or a page swaps in. Attributes only; looks live in the template.
(() => {
  "use strict";
  const menu = document.querySelector("[data-user-menu]");
  if (!menu) return;
  const close = () => menu.removeAttribute("open");
  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.open) {
      close();
      menu.querySelector("summary").focus();
    }
  });
  addEventListener("pointerdown", (event) => {
    if (menu.open && !menu.contains(event.target)) close();
  });
  menu.addEventListener("click", (event) => {
    if (event.target.closest("a[href]")) close();
  });
  // A swap keeps the header, so the server's mark goes stale: mark the link
  // whose URL is the longest prefix of the new address, as the server does.
  const mark = (pathname) => {
    const links = [...menu.querySelectorAll("a[href]")].map((a) => ({ a, path: new URL(a.href).pathname }));
    const best = links.reduce((b, { path }) => (pathname.startsWith(path) && path.length > b.length ? path : b), "");
    links.forEach(({ a, path }) => (best && path === best ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  };
  document.addEventListener("swap:after", (event) => {
    close();
    mark(new URL((event.detail && event.detail.url) || location.href, location.href).pathname);
  });
  addEventListener("popstate", () => mark(location.pathname));
})();
