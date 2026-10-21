const SCALE = 8;
const PAPER = [246, 241, 232];
// Factory default palette, golden, sampled from the device colormap.
const GOLDEN = [0x0004, 0x204a, 0x68d2, 0xb1cd, 0xe2a4, 0xfbe0, 0xfe62, 0xff89, 0xffd2, 0xffff];

const sentenceEl = document.querySelector("#sentence");
const numberEl = document.querySelector("#number");
const unitEl = document.querySelector("#unit");
const smallEl = document.querySelector("#small");
const mapEl = document.querySelector("#map");
const deviceEl = document.querySelector("#device");
const demoEl = document.querySelector("#demo");
const sensitivityEl = document.querySelector("#sensitivity");
const sensitivityReadEl = document.querySelector("#sensitivity-readout");
const intervalEl = document.querySelector("#interval");
const intervalReadEl = document.querySelector("#interval-readout");
const spotEl = document.querySelector("#spot");
const checkEl = document.querySelector("#check");
const tabSpotEl = document.querySelector("#tab-spot");
const tabCheckEl = document.querySelector("#tab-check");
const checkTitleEl = document.querySelector("#check-title");
const checkResultEl = document.querySelector("#check-result");
const checkAverageEl = document.querySelector("#check-average");
const measureStartEl = document.querySelector("#measure-start");
const measureRestartEl = document.querySelector("#measure-restart");
const measureRowsEl = document.querySelector("#measure-rows");

let state = null;
let drag = null;
let socket;

function send(msg) {
  if (socket && socket.readyState === 1) socket.send(JSON.stringify(msg));
}

function rgb565(color) {
  return [
    (((color >> 11) & 31) * 255) / 31,
    (((color >> 5) & 63) * 255) / 63,
    ((color & 31) * 255) / 31,
  ];
}

function colorize(value, lo, hi) {
  const span = hi - lo;
  let t = span <= 0 ? 0.5 : (value - lo) / span;
  t = Math.max(0, Math.min(1, t));
  const pos = t * (GOLDEN.length - 1);
  const index = Math.floor(pos);
  const next = Math.min(GOLDEN.length - 1, index + 1);
  const mix = pos - index;
  const a = rgb565(GOLDEN[index]);
  const b = rgb565(GOLDEN[next]);
  return a.map((channel, i) => Math.round(channel + (b[i] - channel) * mix));
}

function draw(pixels, marks, mask, range, faded) {
  const ctx = mapEl.getContext("2d");
  mapEl.width = 32 * SCALE;
  mapEl.height = 24 * SCALE;
  ctx.imageSmoothingEnabled = false;
  const mark = new Set(marks || []);
  const ignored = new Set(mask || []);
  const lo = range && range.length ? range[0] : 0;
  const hi = range && range.length ? range[1] : 1;
  if (!pixels) {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, mapEl.width, mapEl.height);
    mapEl.classList.toggle("faded", true);
    return;
  }
  mapEl.classList.toggle("faded", faded);
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
  mark.forEach((i) => {
    const x = i % 32;
    const y = (i / 32) | 0;
    const cx = x * SCALE + SCALE / 2;
    const cy = y * SCALE + SCALE / 2;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - 14, cy);
    ctx.lineTo(cx + 14, cy);
    ctx.moveTo(cx, cy - 14);
    ctx.lineTo(cx, cy + 14);
    ctx.stroke();
  });
}

function paint() {
  if (!state) return;
  const down = state.link === "down" || state.status === "down" || state.status === "wait";
  document.body.classList.toggle("down", down);
  demoEl.hidden = !state.demo;
  deviceEl.hidden = !!state.demo;
  sentenceEl.textContent = state.text || "";
  numberEl.textContent = state.number || "";
  unitEl.textContent = state.unit || "";
  smallEl.textContent = state.small || "";
  draw(down ? null : state.pixels, state.marks, state.mask, state.range, down);
  if (document.activeElement !== deviceEl && state.device && deviceEl.value !== state.device) {
    deviceEl.value = state.device;
  }
  if (document.activeElement !== sensitivityEl && !sensitivityEl.dataset.drag && state.sensitivity != null) {
    sensitivityEl.value = String(state.sensitivity);
    sensitivityReadEl.textContent = String(state.sensitivity);
  }
  if (document.activeElement !== intervalEl && !intervalEl.dataset.drag && state.interval != null) {
    intervalEl.value = String(state.interval);
    intervalReadEl.textContent = String(state.interval);
  }
  paintMeasure();
}

function cellText(value) {
  return String(value).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));
}

function paintMeasure() {
  const measure = state.measure || { phase: "idle", rows: [], average: null, fever: false };
  const phase = measure.phase || "idle";
  const live = state.link === "live";
  measureStartEl.hidden = phase !== "idle";
  measureRestartEl.hidden = phase !== "done";
  measureRowsEl.innerHTML = (measure.rows || [])
    .map((row) => `<tr><td>${cellText(row.date)}</td><td>${cellText(row.time)}</td><td>${cellText(row.temp)}°C</td></tr>`)
    .join("");
  checkResultEl.classList.toggle("fever", phase === "done" && !!measure.fever);
  if (!live && phase !== "done") {
    checkTitleEl.textContent = state.text || "尚未連接。";
    checkResultEl.textContent = "";
    checkAverageEl.textContent = "";
    return;
  }
  if (phase === "run") {
    checkTitleEl.textContent = "記錄中。";
    checkResultEl.textContent = "";
    checkAverageEl.textContent = "";
    return;
  }
  if (phase === "done" && measure.fever) {
    checkTitleEl.textContent = "十秒測溫";
    checkResultEl.textContent = "您發燒了";
    checkAverageEl.textContent = `平均 ${Number(measure.average).toFixed(1)}°C`;
    return;
  }
  if (phase === "done") {
    checkTitleEl.textContent = "十秒測溫";
    checkResultEl.textContent = "完成。";
    checkAverageEl.textContent = `平均 ${Number(measure.average).toFixed(1)}°C`;
    return;
  }
  checkTitleEl.textContent = "按開始，記錄 10 秒。";
  checkResultEl.textContent = "";
  checkAverageEl.textContent = "";
}

document.querySelector("#clearmask").addEventListener("click", () => send({ op: "clearmask" }));

function bindSlider(el, readout, op, key) {
  el.addEventListener("pointerdown", () => {
    el.dataset.drag = "1";
  });
  el.addEventListener("input", () => {
    readout.textContent = el.value;
    send({ op, [key]: Number(el.value) });
  });
}

window.addEventListener("pointerup", () => {
  delete sensitivityEl.dataset.drag;
  delete intervalEl.dataset.drag;
});

bindSlider(sensitivityEl, sensitivityReadEl, "sensitivity", "sensitivity");
bindSlider(intervalEl, intervalReadEl, "interval", "interval");

function showMenu(name) {
  const check = name === "check";
  spotEl.hidden = check;
  checkEl.hidden = !check;
  tabSpotEl.classList.toggle("on", !check);
  tabCheckEl.classList.toggle("on", check);
}

tabSpotEl.addEventListener("click", () => showMenu("spot"));
tabCheckEl.addEventListener("click", () => showMenu("check"));

function beginMeasure() {
  if (!state || state.link !== "live") return;
  send({ op: "measure", action: "start" });
}

measureStartEl.addEventListener("click", beginMeasure);
measureRestartEl.addEventListener("click", beginMeasure);

function commitDevice() {
  send({ op: "url", url: deviceEl.value });
}

deviceEl.addEventListener("change", commitDevice);
deviceEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter") commitDevice();
});

function cellAt(event) {
  const rect = mapEl.getBoundingClientRect();
  const x = Math.floor(((event.clientX - rect.left) / rect.width) * 32);
  const y = Math.floor(((event.clientY - rect.top) / rect.height) * 24);
  if (x < 0 || y < 0 || x > 31 || y > 23) return null;
  return { x, y };
}

mapEl.addEventListener("pointerdown", (event) => {
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

function connect() {
  socket = new WebSocket(`ws://${location.host}/`);
  socket.onmessage = (message) => {
    state = JSON.parse(message.data);
    paint();
  };
  socket.onclose = () => setTimeout(connect, 800);
}

connect();
