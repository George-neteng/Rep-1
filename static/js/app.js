const $ = (id) => document.getElementById(id);

const fileInput = $("fileInput");
const dropZone  = $("dropZone");
const runBtn    = $("runBtn");
const statusEl  = $("status");
const confRange = $("confRange");

let currentFile = null;

// ---------- выбор файла ----------
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => setFile(fileInput.files[0]));

["dragover", "dragenter"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("drag"); }));
dropZone.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

function setFile(f) {
  if (!f) return;
  currentFile = f;
  $("fileName").textContent = f.name;
  runBtn.disabled = false;
  setStatus("");
}

confRange.addEventListener("input", () => { $("confVal").textContent = confRange.value; });

// ---------- обработка ----------
runBtn.addEventListener("click", async () => {
  if (!currentFile) return;
  runBtn.disabled = true;
  setStatus("Обработка… для видео это может занять время", "work");

  const fd = new FormData();
  fd.append("file", currentFile);
  fd.append("conf", confRange.value);

  try {
    const res = await fetch("/process", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Ошибка сервера");
    renderResult(data);
    setStatus(`Готово за ${data.elapsed} с`, "ok");
    loadHistory();
  } catch (e) {
    setStatus(e.message, "err");
  } finally {
    runBtn.disabled = false;
  }
});

function setStatus(text, cls = "") {
  statusEl.textContent = text;
  statusEl.className = "status " + cls;
}

// ---------- результат ----------
function renderResult(data) {
  const box = $("resultBox");
  box.classList.remove("empty");
  const url = data.result_url + "?t=" + Date.now();
  box.innerHTML = data.media === "video"
    ? `<video src="${url}" controls autoplay muted loop></video>`
    : `<img src="${url}" alt="Результат">`;

  $("pdfBtn").href  = `/report/pdf/${data.id}`;
  $("xlsxBtn").href = `/report/xlsx/${data.id}`;
  $("reportBtns").classList.remove("hidden");

  renderStats(data.stats);
}

function row(k, v, cls = "") {
  return `<div class="stat-row"><span class="k">${k}</span><span class="v ${cls}">${v}</span></div>`;
}

function renderStats(s) {
  const box = $("statsBox");
  let html = "";

  if ("ball_found" in s)
    html += row("Мяч найден", s.ball_found ? "да" : "нет", s.ball_found ? "yes" : "no");
  if ("players" in s)        html += row("Игроков в кадре", s.players);
  if ("ball_zone" in s)      html += row("Зона мяча", s.ball_zone);
  if ("ball_center" in s)    html += row("Центр мяча (px)", s.ball_center.join(", "));
  if ("ball_norm" in s)      html += row("Норм. координаты", s.ball_norm.join(", "));
  if ("ball_conf" in s)      html += row("Уверенность", s.ball_conf);
  if ("nearest_player_dist_px" in s)
    html += row("До ближнего игрока (px)", s.nearest_player_dist_px);

  // видео
  if ("frames_processed" in s)   html += row("Кадров обработано", s.frames_processed);
  if ("ball_visibility_pct" in s) html += row("Видимость мяча", s.ball_visibility_pct + " %");
  if ("ball_distance_px" in s)   html += row("Путь мяча (px)", s.ball_distance_px);
  if ("dominant_zone" in s)      html += row("Доминирующая зона", s.dominant_zone);

  box.innerHTML = html || '<span class="muted">Нет данных</span>';

  // тепловая сетка зон (для видео)
  const grid = $("zoneGrid");
  if (s.zone_distribution) {
    const flat = s.zone_distribution.flat();
    const max = Math.max(...flat, 1);
    grid.innerHTML = s.zone_distribution.flat().map(v => {
      const a = (0.15 + 0.85 * v / max).toFixed(2);
      return `<div class="zone-cell" style="background:rgba(46,160,67,${a})">${v}</div>`;
    }).join("");
    grid.classList.remove("hidden");

    if (s.heatmap_url) {
      box.innerHTML += row("Тепловая карта", `<a href="${s.heatmap_url}" target="_blank">открыть</a>`);
    }
  } else {
    grid.classList.add("hidden");
  }
}

// ---------- история ----------
async function loadHistory() {
  try {
    const res = await fetch("/history");
    const items = await res.json();
    const box = $("historyBox");
    if (!items.length) { box.innerHTML = '<span class="muted">Пока пусто</span>'; return; }
    box.innerHTML =
      "<table><thead><tr><th>Время</th><th>Файл</th><th>Тип</th>" +
      "<th>Сек</th><th>Зона / мяч</th><th>Отчёт</th></tr></thead><tbody>" +
      items.map(it => {
        const z = it.stats.ball_zone || it.stats.dominant_zone ||
                  (it.stats.ball_found ? "—" : "нет мяча");
        return `<tr>
          <td>${it.timestamp.replace("T", " ")}</td>
          <td>${it.filename}</td>
          <td>${it.media}</td>
          <td>${it.elapsed}</td>
          <td>${z}</td>
          <td><a href="/report/pdf/${it.id}">PDF</a> ·
              <a href="/report/xlsx/${it.id}">XLSX</a></td>
        </tr>`;
      }).join("") + "</tbody></table>";
  } catch {
    $("historyBox").innerHTML = '<span class="muted">Не удалось загрузить</span>';
  }
}

loadHistory();
