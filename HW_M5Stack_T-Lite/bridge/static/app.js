const SCALE = 8;
const COOL = [239, 230, 214];
const WARM = [107, 36, 16];
const PAPER = [246, 241, 232];
const MARK = [154, 52, 18];

const sentenceEl = document.querySelector("#sentence");
const numberEl = document.querySelector("#number");
const unitEl = document.querySelector("#unit");
const smallEl = document.querySelector("#small");
const mapEl = document.querySelector("#map");
const nameEl = document.querySelector("#name");
const screens = {
  now: document.querySelector("#now"),
  compare: document.querySelector("#compare"),
  events: document.querySelector("#events"),
  report: document.querySelector("#report"),
};

let state = null;
let screen = "now";
let drag = null;

function send(msg) {
  if (socket && socket.readyState === 1) {
    socket.send(JSON.stringify(msg));
  }
}

function colorize(value, lo, hi) {
  const span = hi - lo;
  let t = span <= 0 ? 0.5 : (value - lo) / span;
  t = Math.max(0, Math.min(1, t));
  return COOL.map((c, i) => Math.round(c + (WARM[i] - c) * t));
}

function draw(canvas, pixels, marks, mask, range, faded) {
  const ctx = canvas.getContext("2d");
  canvas.width = 32 * SCALE;
  canvas.height = 24 * SCALE;
  ctx.imageSmoothingEnabled = false;
  const mark = new Set(marks || []);
  const ignored = new Set(mask || []);
  const lo = range && range.length ? range[0] : 0;
  const hi = range && range.length ? range[1] : 1;
  if (!pixels) {
    ctx.fillStyle = "#efe6d6";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    canvas.classList.toggle("faded", true);
    return;
  }
  canvas.classList.toggle("faded", faded);
  for (let i = 0; i < pixels.length; i++) {
    const x = i % 32;
    const y = (i / 32) | 0;
    let [r, g, b] = colorize(pixels[i], lo, hi);
    if (ignored.has(i)) {
      r = (r + PAPER[0]) >> 1;
      g = (g + PAPER[1]) >> 1;
      b = (b + PAPER[2]) >> 1;
    }
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(x * SCALE, y * SCALE, SCALE, SCALE);
  }
  ctx.fillStyle = `rgb(${MARK[0]},${MARK[1]},${MARK[2]})`;
  mark.forEach((i) => {
    const x = i % 32;
    const y = (i / 32) | 0;
    if (!mark.has(i - 32)) ctx.fillRect(x * SCALE, y * SCALE, SCALE, 1);
    if (!mark.has(i + 32)) ctx.fillRect(x * SCALE, y * SCALE + SCALE - 1, SCALE, 1);
    if (x === 0 || !mark.has(i - 1)) ctx.fillRect(x * SCALE, y * SCALE, 1, SCALE);
    if (x === 31 || !mark.has(i + 1)) ctx.fillRect(x * SCALE + SCALE - 1, y * SCALE, 1, SCALE);
  });
}

function show(name) {
  screen = name;
  Object.entries(screens).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
  document.querySelectorAll("#screens button").forEach((button) => {
    button.classList.toggle("on", button.dataset.screen === name);
  });
  paint();
}

function paint() {
  if (!state) return;
  const down = state.link === "down";
  document.body.classList.toggle("down", down);
  document.querySelector("#demo").hidden = !state.demo;
  sentenceEl.textContent = state.sentence || "";
  sentenceEl.classList.toggle("hot", !!state.emphasis);
  numberEl.textContent = state.number || "";
  unitEl.textContent = state.number ? state.unit || "" : "";
  smallEl.textContent = down ? "" : state.small || "";
  const liveRange = state.pixels ? [Math.min(...state.pixels), Math.max(...state.pixels)] : [0, 1];
  draw(mapEl, down ? null : state.pixels, state.marks, state.work === "sentry" ? state.mask : [], liveRange, down);

  document.querySelector("#memory-tools").hidden = state.work !== "memory";
  document.querySelector("#sentry-tools").hidden = state.work !== "sentry";
  document.querySelectorAll("#works button").forEach((button) => {
    button.classList.toggle("on", button.dataset.work === state.work);
  });
  document.querySelectorAll("#distances button").forEach((button) => {
    button.classList.toggle("on", button.dataset.distance === state.distance);
  });
  document.querySelectorAll("#materials button").forEach((button) => {
    button.classList.toggle("on", button.dataset.material === state.material);
  });
  document.querySelectorAll("#levels button").forEach((button) => {
    button.classList.toggle("on", Number(button.dataset.sensitivity) === state.sensitivity);
  });
  if (document.activeElement !== nameEl && nameEl.value !== (state.name || "")) {
    nameEl.value = state.name || "";
  }

  const both = state.range && state.range.length ? state.range : liveRange;
  document.querySelector("#compare-sentence").textContent = state.sentence || "";
  document.querySelector("#compare-sentence").classList.toggle("hot", !!state.emphasis);
  draw(document.querySelector("#map-now"), down ? null : state.pixels, [], [], both, down);
  draw(document.querySelector("#map-last"), state.last_pixels, [], [], both, false);

  const list = document.querySelector("#event-list");
  const html = (state.events || []).map((item) => (
    `<li><button type="button" data-event="${item.id}">${item.taken_at}　${item.sentence}</button></li>`
  )).join("");
  if (list.dataset.html !== html) {
    list.dataset.html = html;
    list.innerHTML = html || "<li><button type=\"button\" disabled>還沒有經過。</button></li>";
  }
  const picked = state.selected_event;
  const eventMap = document.querySelector("#map-event");
  if (picked && picked.pixels) {
    eventMap.hidden = false;
    const range = [Math.min(...picked.pixels), Math.max(...picked.pixels)];
    draw(eventMap, picked.pixels, [], [], range, false);
  } else {
    eventMap.hidden = true;
  }

  document.querySelector("#report-sentence").textContent = state.sentence || "";
  document.querySelector("#report-sentence").classList.toggle("hot", !!state.emphasis);
  const reportNumber = [state.number, state.unit].filter(Boolean).join(" ");
  document.querySelector("#report-number").textContent = reportNumber;
  const material = {
    plastic: "塑膠", painted: "塗裝金屬", pcb: "電路板", water: "水", shiny: "光亮金屬",
  }[state.material] || "";
  const emis = state.emissivity_milli == null ? "沒有可靠的發射率" : (state.emissivity_milli / 1000).toFixed(2);
  const reflected = state.reflected_cdeg == null ? "等於感測器環境溫度" : `${(state.reflected_cdeg / 100).toFixed(1)}°C`;
  document.querySelector("#report-small").textContent = [
    material,
    `發射率 ${emis}`,
    `反射溫度 ${reflected}`,
    state.small || "",
    `裝置 ${state.mac || "尚未讀到"}`,
    "篩查用，非計量追溯",
  ].filter(Boolean).map((part) => part.replace(/。+$/, "")).join("。") + "。";
  draw(document.querySelector("#map-report"), down ? null : state.pixels, state.marks, state.work === "sentry" ? state.mask : [], liveRange, down);
}

document.querySelector("#works").addEventListener("click", (event) => {
  const work = event.target.dataset.work;
  if (work) send({ op: "work", work });
});

document.querySelector("#screens").addEventListener("click", (event) => {
  const next = event.target.dataset.screen;
  if (next) show(next);
});

document.querySelector("#distances").addEventListener("click", (event) => {
  const distance = event.target.dataset.distance;
  if (distance) send({ op: "distance", distance });
});

document.querySelector("#materials").addEventListener("click", (event) => {
  const material = event.target.dataset.material;
  if (material) send({ op: "material", material });
});

document.querySelector("#levels").addEventListener("click", (event) => {
  const sensitivity = event.target.dataset.sensitivity;
  if (sensitivity != null && event.target.dataset.sensitivity !== undefined && event.target.matches("button")) {
    send({ op: "sensitivity", sensitivity: Number(sensitivity) });
  }
});

nameEl.addEventListener("change", () => send({ op: "name", name: nameEl.value }));
nameEl.addEventListener("blur", () => send({ op: "name", name: nameEl.value }));
document.querySelector("#remember").addEventListener("click", () => {
  send({ op: "name", name: nameEl.value });
  send({ op: "remember" });
});
document.querySelector("#disarm").addEventListener("click", () => send({ op: "arm", armed: false }));
document.querySelector("#clearmask").addEventListener("click", () => send({ op: "mask", cells: [] }));

document.querySelector("#event-list").addEventListener("click", (event) => {
  const id = event.target.dataset.event;
  if (id) send({ op: "event", id: Number(id) });
});

document.querySelector("#save-pdf").addEventListener("click", async () => {
  const response = await fetch("/api/report.pdf");
  const type = response.headers.get("content-type") || "";
  if (type.includes("pdf")) {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "thermal-memory.pdf";
    link.click();
    URL.revokeObjectURL(url);
    return;
  }
  window.print();
});

function cellAt(event) {
  const rect = mapEl.getBoundingClientRect();
  const x = Math.floor(((event.clientX - rect.left) / rect.width) * 32);
  const y = Math.floor(((event.clientY - rect.top) / rect.height) * 24);
  if (x < 0 || y < 0 || x > 31 || y > 23) return null;
  return { x, y };
}

mapEl.addEventListener("pointerdown", (event) => {
  if (!state || state.work !== "sentry") return;
  const cell = cellAt(event);
  if (!cell) return;
  drag = cell;
  mapEl.setPointerCapture(event.pointerId);
});

mapEl.addEventListener("pointerup", (event) => {
  if (!drag) return;
  const end = cellAt(event) || drag;
  const x0 = Math.min(drag.x, end.x);
  const x1 = Math.max(drag.x, end.x);
  const y0 = Math.min(drag.y, end.y);
  const y1 = Math.max(drag.y, end.y);
  const cells = [];
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) cells.push(y * 32 + x);
  }
  drag = null;
  send({ op: "mask", cells });
});

let socket;
function connect() {
  socket = new WebSocket(`ws://${location.host}/`);
  socket.onmessage = (message) => {
    state = JSON.parse(message.data);
    paint();
  };
  socket.onclose = () => {
    setTimeout(connect, 800);
  };
}
connect();
show("now");
