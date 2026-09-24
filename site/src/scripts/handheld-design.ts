const device = document.querySelector<HTMLElement>("#device");
if (device) {
  const cards = Array.from(device.querySelectorAll<HTMLElement>("[data-card]"));
  const demos = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-demo]"));
  const order = ["terminal", "monitor", "video"];
  const names: Record<string, [string, string, string]> = {
    terminal: ["Terminal", "Foot", "foot"], monitor: ["Monitor", "htop", "htop"], video: ["Video", "mpv", "mpv"],
    files: ["Files", "nnn", "files"], editor: ["Editor", "nano", "editor"], help: ["Help", "Built in", "help"],
  };
  const assetBase = (device.querySelector<HTMLImageElement>(".active-icon")?.src ?? "").replace(/foot\.svg$/, "");
  let selected = 0;
  let priorView = "deck";
  let pending: number[] = [];
  let toastTimer = 0;
  let lastGestureAt = 0;
  const delay = (fn: () => void, ms: number) => { const id = window.setTimeout(fn, ms); pending.push(id); };
  const clearSequence = () => { pending.forEach(window.clearTimeout); pending = []; device.classList.remove("is-throwing", "is-returning"); };
  const view = (name: string) => { device.dataset.view = name; };
  const toast = (message: string) => {
    const el = device.querySelector<HTMLElement>(".toast"); if (!el) return;
    el.textContent = message; el.classList.add("visible"); window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => el.classList.remove("visible"), 2300);
  };
  const renderCards = () => {
    cards.forEach(card => {
      const at = order.indexOf(card.dataset.card ?? "");
      const difference = at - selected;
      card.dataset.position = at < 0 ? "hidden" : difference === 0 ? "center" : difference === -1 ? "left" : difference === 1 ? "right" : "hidden";
    });
    device.querySelector<HTMLElement>(".open-count")!.textContent = `${["Zero", "One", "Two", "Three", "Four", "Five", "Six"][order.length]} ${order.length === 1 ? "app is" : "apps are"}`;
  };
  const choose = (index: number) => { selected = Math.max(0, Math.min(order.length - 1, index)); renderCards(); };
  const activate = (id: string) => {
    if (names[id] && !order.includes(id)) {
      order.push(id); order.sort((a, b) => ["terminal", "monitor", "video", "files", "editor", "help"].indexOf(a) - ["terminal", "monitor", "video", "files", "editor", "help"].indexOf(b));
    }
    const [title, subtitle, icon] = names[id] ?? [id, "App", "help"];
    device.dataset.active = id;
    device.querySelector<HTMLElement>(".active-title")!.textContent = title;
    device.querySelector<HTMLElement>(".active-subtitle")!.textContent = subtitle;
    device.querySelector<HTMLImageElement>(".active-icon")!.src = `${assetBase}${icon}.svg`;
    device.querySelector<HTMLImageElement>(".generic-active-icon")!.src = `${assetBase}${icon}.svg`;
    device.querySelector<HTMLElement>(".generic-heading")!.textContent = title;
    const at = order.indexOf(id); if (at >= 0) choose(at);
    view("app");
  };
  const home = () => {
    const glass = device.querySelector<HTMLElement>(".glass")!;
    const target = centerCard() ?? cards[0];
    const outer = glass.getBoundingClientRect();
    const inner = target.getBoundingClientRect();
    const dx = inner.left + inner.width / 2 - (outer.left + outer.width / 2);
    const dy = inner.top + inner.height / 2 - (outer.top + outer.height / 2);
    deckLayer.style.transition = "opacity .45s ease, transform .55s ease";
    deckLayer.style.opacity = "1"; deckLayer.style.transform = "none";
    appLayer.style.transition = "transform .55s cubic-bezier(.2,.8,.2,1), opacity .55s ease";
    appLayer.style.transform = `translate(${dx}px, ${dy}px) scale(${inner.width / outer.width}, ${inner.height / outer.height})`;
    appLayer.style.opacity = "0";
    delay(() => { view("deck"); resetDrag(); }, 560);
  };
  const drawer = () => view("drawer");
  const shade = () => { priorView = device.dataset.view ?? "deck"; view("shade"); };
  const throwCard = () => {
    const id = order[selected];
    if (id === "monitor") { toast("Monitor is busy. It stays in the deck."); return; }
    device.classList.add("is-throwing");
    delay(() => {
      const index = order.indexOf(id); if (index >= 0) order.splice(index, 1);
      const card = cards.find(c => c.dataset.card === id); if (card) card.dataset.position = "hidden";
      choose(Math.min(selected, order.length - 1)); device.classList.remove("is-throwing");
      toast(`${names[id][0]} closed`);
    }, 540);
  };
  cards.forEach(card => card.addEventListener("click", () => {
    if (performance.now() - lastGestureAt < 350) return;
    const index = order.indexOf(card.dataset.card ?? "");
    if (index < 0) return;
    if (index !== selected) choose(index); else activate(order[selected]);
  }));
  device.querySelectorAll<HTMLElement>("[data-launch]").forEach(app => app.addEventListener("click", () => activate(app.dataset.launch ?? "terminal")));
  demos.forEach(button => button.addEventListener("click", () => {
    clearSequence(); order.splice(0, order.length, "terminal", "monitor", "video"); choose(0);
    demos.forEach(b => b.removeAttribute("aria-current")); button.setAttribute("aria-current", "true");
    switch (button.dataset.demo) {
      case "home": activate("terminal"); delay(home, 550); break;
      case "swipe": view("deck"); choose(0); delay(() => choose(1), 500); delay(() => choose(2), 1200); break;
      case "drawer": view("deck"); delay(drawer, 550); break;
      case "expand": view("deck"); choose(Math.max(0, order.indexOf("terminal"))); delay(() => activate(order[selected]), 650); break;
      case "throw": view("deck"); choose(Math.max(0, order.indexOf("monitor"))); delay(throwCard, 500); delay(() => { const at = order.indexOf("video"); if (at >= 0) { choose(at); delay(throwCard, 650); } }, 2550); break;
      case "shade": view("deck"); delay(shade, 550); break;
    }
  }));
  let start: { x: number; y: number; at: number; pointer: number; dragging: boolean } | null = null;
  const deckLayer = device.querySelector<HTMLElement>(".deck-view")!;
  const appLayer = device.querySelector<HTMLElement>(".app-view")!;
  const drawerLayer = device.querySelector<HTMLElement>(".drawer-view")!;
  const shadeLayer = device.querySelector<HTMLElement>(".shade-view")!;
  const centerCard = () => cards.find(card => card.dataset.position === "center");
  const resetDrag = () => {
    [deckLayer, appLayer, drawerLayer, shadeLayer, ...cards].forEach(el => { el.style.removeProperty("transform"); el.style.removeProperty("opacity"); el.style.removeProperty("transition"); el.style.removeProperty("pointer-events"); });
  };
  device.querySelector("#open-settings")?.addEventListener("click", () => view("settings"));
  device.querySelector("#settings-back")?.addEventListener("click", () => view("shade"));
  device.addEventListener("pointerdown", e => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (start) { start = null; resetDrag(); return; }
    start = { x: e.clientX, y: e.clientY, at: e.clientY - device.getBoundingClientRect().top, pointer: e.pointerId, dragging: false };
  });
  device.addEventListener("pointermove", e => {
    if (!start || e.pointerId !== start.pointer) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (!start.dragging && Math.hypot(dx, dy) < 8) return;
    if (!start.dragging) { start.dragging = true; device.setPointerCapture(e.pointerId); clearSequence(); }
    const current = device.dataset.view;
    const fromTop = start.at < device.clientHeight * .16;
    const fromBottom = start.at > device.clientHeight * .76;
    if (current === "app" && dy < 0 && fromBottom) {
      const p = Math.min(1, -dy / (device.clientHeight * .42));
      deckLayer.style.transition = "none"; deckLayer.style.opacity = `${p}`; deckLayer.style.transform = `scale(${.9 + .1 * p})`;
      appLayer.style.transition = "none"; appLayer.style.transform = `translateY(${dy * .18}px) scale(${1 - .28 * p})`; appLayer.style.opacity = `${1 - .26 * p}`;
    } else if (current === "deck" && Math.abs(dx) > Math.abs(dy)) {
      const card = centerCard(); if (card) { card.style.transition = "none"; card.style.transform = `translateX(${Math.max(-120, Math.min(120, dx))}px) scale(.98)`; }
    } else if (current === "deck" && dy < 0 && fromBottom) {
      const p = Math.min(1, -dy / (device.clientHeight * .42));
      drawerLayer.style.transition = "none"; drawerLayer.style.opacity = `${p}`; drawerLayer.style.transform = `translateY(${(1 - p) * 100}%)`;
    } else if (dy > 0 && fromTop && current !== "shade") {
      const p = Math.min(1, dy / (device.clientHeight * .42));
      shadeLayer.style.transition = "none"; shadeLayer.style.opacity = `${p}`; shadeLayer.style.transform = `translateY(${(-1 + p) * 100}%)`;
    } else if (current === "deck" && dy < 0) {
      const card = centerCard(); if (card) { card.style.transition = "none"; card.style.transform = `translateY(${Math.max(-180, dy)}px) rotate(${Math.max(-8, dy / 25)}deg)`; }
    }
  });
  device.addEventListener("pointerup", e => {
    if (!start || e.pointerId !== start.pointer) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    const fromTop = start.at < device.clientHeight * .16;
    const fromBottom = start.at > device.clientHeight * .76;
    const current = device.dataset.view;
    const wasDragging = start.dragging; start = null;
    if (wasDragging) lastGestureAt = performance.now();
    if (Math.abs(dx) < 35 && Math.abs(dy) < 40) { resetDrag(); return; }
    lastGestureAt = performance.now();
    clearSequence();
    if (current === "app" && dy < -50 && fromBottom) { home(); return; }
    resetDrag();
    if (dy > 55 && fromTop && current !== "shade") { shade(); return; }
    if (current === "settings") { if (dy < -50 && fromBottom) view("deck"); else if (dy > 45) view("shade"); return; }
    if (current === "shade") { if (dy < -45) view(priorView); return; }
    if (current === "app") return;
    if (current === "drawer") { if (dy > 45) view("deck"); return; }
    if (current === "deck") {
      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 45) { choose(selected + (dx < 0 ? 1 : -1)); return; }
      if (dy < -65) { if (fromBottom) drawer(); else throwCard(); }
    }
  });
  device.addEventListener("pointercancel", () => { start = null; resetDrag(); });
  device.addEventListener("keydown", e => {
    if (e.key === "Escape") { clearSequence(); view("deck"); }
    if (e.key === "ArrowLeft") choose(selected - 1);
    if (e.key === "ArrowRight") choose(selected + 1);
    if (e.key === "Enter" && device.dataset.view === "deck") activate(order[selected]);
  });
  renderCards();
}
