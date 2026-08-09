"use strict";

const state = {
  jobId: null,
  pageCount: 0,
  pages: [],
  removedPages: new Set(), // 0-indexed
  boxes: new Map(), // 0-indexed page -> [{x0,y0,x1,y1}]
  currentEditingPage: null,
};

function showSection(id) {
  for (const el of document.querySelectorAll("main > section")) {
    el.hidden = el.id !== id;
  }
}

function showError(id, message) {
  const el = document.getElementById(id);
  el.textContent = message;
  el.hidden = false;
}

function hideError(id) {
  const el = document.getElementById(id);
  el.hidden = true;
  el.textContent = "";
}

function clamp01(v) {
  return Math.max(0, Math.min(1, v));
}

// --- ページ範囲のパース/フォーマット (1-indexed の "3,5-7" 形式 <-> 0-indexed Set) ---

function parseRangeSpec(spec) {
  const result = new Set();
  for (const rawPart of spec.split(",")) {
    const part = rawPart.trim();
    if (!part) continue;
    if (part.includes("-")) {
      const [startStr, endStr] = part.split("-");
      const start = parseInt(startStr, 10);
      const end = parseInt(endStr, 10);
      if (!Number.isNaN(start) && !Number.isNaN(end) && start >= 1 && end >= start) {
        for (let p = start; p <= end; p++) result.add(p - 1);
      }
    } else {
      const p = parseInt(part, 10);
      if (!Number.isNaN(p) && p >= 1) result.add(p - 1);
    }
  }
  return result;
}

function formatRangeSpec(zeroIndexedSet) {
  const pages = Array.from(zeroIndexedSet)
    .map((p) => p + 1)
    .sort((a, b) => a - b);
  if (pages.length === 0) return "";
  const ranges = [];
  let start = pages[0];
  let prev = pages[0];
  for (let i = 1; i <= pages.length; i++) {
    const cur = pages[i];
    if (cur === prev + 1) {
      prev = cur;
      continue;
    }
    ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
    if (cur !== undefined) {
      start = cur;
      prev = cur;
    }
  }
  return ranges.join(",");
}

function syncRangeInputFromState() {
  document.getElementById("remove-range-input").value = formatRangeSpec(state.removedPages);
}

function toggleRemoved(pageIndex) {
  if (state.removedPages.has(pageIndex)) {
    state.removedPages.delete(pageIndex);
  } else {
    state.removedPages.add(pageIndex);
  }
  syncRangeInputFromState();
  renderThumbnails();
}

// --- サムネイル一覧 ---

function renderThumbnails() {
  const container = document.getElementById("thumbnails");
  container.innerHTML = "";
  for (let i = 0; i < state.pageCount; i++) {
    const card = document.createElement("div");
    card.className = "thumb-card";
    if (state.removedPages.has(i)) card.classList.add("removed");

    const img = document.createElement("img");
    img.src = `/api/job/${state.jobId}/preview/${i}`;
    img.alt = `ページ ${i + 1}`;
    img.addEventListener("click", () => toggleRemoved(i));
    card.appendChild(img);

    const label = document.createElement("div");
    label.className = "thumb-label";
    label.textContent = `${i + 1}`;
    card.appendChild(label);

    const boxCount = (state.boxes.get(i) || []).length;
    if (boxCount > 0) {
      const badge = document.createElement("div");
      badge.className = "thumb-badge";
      badge.textContent = `矩形${boxCount}`;
      card.appendChild(badge);
    }

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "thumb-edit-button";
    editButton.textContent = "矩形編集";
    editButton.addEventListener("click", (e) => {
      e.stopPropagation();
      openBoxEditor(i);
    });
    card.appendChild(editButton);

    container.appendChild(card);
  }
}

// --- 矩形エディタ ---

function openBoxEditor(pageIndex) {
  state.currentEditingPage = pageIndex;
  document.getElementById("box-editor-page-label").textContent = `ページ ${pageIndex + 1}`;
  document.getElementById("box-editor-image").src =
    `/api/job/${state.jobId}/preview/${pageIndex}`;
  document.getElementById("box-editor-overlay").hidden = false;
  renderBoxList();
  renderDrawnBoxes();
}

function closeBoxEditor() {
  document.getElementById("box-editor-overlay").hidden = true;
  state.currentEditingPage = null;
  renderThumbnails();
}

function renderDrawnBoxes() {
  const layer = document.getElementById("box-editor-draw-layer");
  layer.innerHTML = "";
  const boxes = state.boxes.get(state.currentEditingPage) || [];
  for (const box of boxes) {
    const el = document.createElement("div");
    el.className = "drawn-box";
    el.style.left = `${box.x0 * 100}%`;
    el.style.top = `${box.y0 * 100}%`;
    el.style.width = `${(box.x1 - box.x0) * 100}%`;
    el.style.height = `${(box.y1 - box.y0) * 100}%`;
    layer.appendChild(el);
  }
}

function renderBoxList() {
  const list = document.getElementById("box-list");
  list.innerHTML = "";
  const boxes = state.boxes.get(state.currentEditingPage) || [];
  boxes.forEach((box, idx) => {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent =
      `矩形 ${idx + 1}: (${box.x0.toFixed(2)}, ${box.y0.toFixed(2)}) - ` +
      `(${box.x1.toFixed(2)}, ${box.y1.toFixed(2)})`;
    li.appendChild(label);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "削除";
    delBtn.addEventListener("click", () => {
      boxes.splice(idx, 1);
      renderBoxList();
      renderDrawnBoxes();
    });
    li.appendChild(delBtn);
    list.appendChild(li);
  });
}

function setupDrawLayer() {
  const layer = document.getElementById("box-editor-draw-layer");
  let startX = 0;
  let startY = 0;
  let tempEl = null;

  layer.addEventListener("mousedown", (e) => {
    if (state.currentEditingPage === null) return;
    const rect = layer.getBoundingClientRect();
    startX = clamp01((e.clientX - rect.left) / rect.width);
    startY = clamp01((e.clientY - rect.top) / rect.height);
    tempEl = document.createElement("div");
    tempEl.className = "drawn-box drawing";
    layer.appendChild(tempEl);
  });

  layer.addEventListener("mousemove", (e) => {
    if (!tempEl) return;
    const rect = layer.getBoundingClientRect();
    const curX = clamp01((e.clientX - rect.left) / rect.width);
    const curY = clamp01((e.clientY - rect.top) / rect.height);
    const x0 = Math.min(startX, curX);
    const y0 = Math.min(startY, curY);
    const x1 = Math.max(startX, curX);
    const y1 = Math.max(startY, curY);
    tempEl.style.left = `${x0 * 100}%`;
    tempEl.style.top = `${y0 * 100}%`;
    tempEl.style.width = `${(x1 - x0) * 100}%`;
    tempEl.style.height = `${(y1 - y0) * 100}%`;
    tempEl.dataset.x0 = String(x0);
    tempEl.dataset.y0 = String(y0);
    tempEl.dataset.x1 = String(x1);
    tempEl.dataset.y1 = String(y1);
  });

  window.addEventListener("mouseup", () => {
    if (!tempEl) return;
    const x0 = parseFloat(tempEl.dataset.x0);
    const y0 = parseFloat(tempEl.dataset.y0);
    const x1 = parseFloat(tempEl.dataset.x1);
    const y1 = parseFloat(tempEl.dataset.y1);
    tempEl = null;

    if (Number.isNaN(x0) || x1 - x0 < 0.005 || y1 - y0 < 0.005) {
      renderDrawnBoxes(); // 小さすぎる矩形(誤クリック等)は無視
      return;
    }
    const pageIndex = state.currentEditingPage;
    if (!state.boxes.has(pageIndex)) state.boxes.set(pageIndex, []);
    state.boxes.get(pageIndex).push({ x0, y0, x1, y1 });
    renderBoxList();
    renderDrawnBoxes();
  });
}

// --- オプション表示制御 ---

function updateTextLayerDependentUI() {
  const textLayer = document.getElementById("text-layer-select").value;
  document.getElementById("ocr-lang-label").hidden = textLayer !== "ocr";
  const auditCheckbox = document.getElementById("audit-checkbox");
  auditCheckbox.disabled = textLayer !== "extract";
  if (textLayer !== "extract") auditCheckbox.checked = false;
}

// --- アップロード ---

async function uploadFile(file) {
  hideError("upload-error");
  const formData = new FormData();
  formData.append("file", file);

  let res;
  try {
    res = await fetch("/api/upload", { method: "POST", body: formData });
  } catch {
    showError("upload-error", "サーバーに接続できませんでした");
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "アップロードに失敗しました" }));
    showError("upload-error", err.detail || "アップロードに失敗しました");
    return;
  }

  const data = await res.json();
  state.jobId = data.jobId;
  state.pageCount = data.pageCount;
  state.pages = data.pages;
  state.removedPages = new Set();
  state.boxes = new Map();

  document.getElementById("remove-range-input").value = "";
  renderThumbnails();
  showSection("edit-section");
}

// --- 生成・進捗・結果 ---

async function startGenerate() {
  const textLayer = document.getElementById("text-layer-select").value;
  const fill = document.getElementById("fill-select").value;
  const dpi = parseInt(document.getElementById("dpi-select").value, 10);
  const ocrLang = document.getElementById("ocr-lang-input").value.trim() || "eng";
  const markdown = document.getElementById("markdown-checkbox").checked;
  const audit = document.getElementById("audit-checkbox").checked;

  const removePages = Array.from(state.removedPages).map((p) => p + 1);
  const boxesPayload = {};
  state.boxes.forEach((boxList, pageIndex) => {
    if (boxList.length === 0) return;
    boxesPayload[String(pageIndex + 1)] = boxList.map((b) => [b.x0, b.y0, b.x1, b.y1]);
  });

  hideError("render-error");
  let res;
  try {
    res = await fetch(`/api/job/${state.jobId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        removePages,
        boxes: boxesPayload,
        textLayer,
        fill,
        dpi,
        ocrLang,
        markdown,
        audit,
      }),
    });
  } catch {
    showError("render-error", "サーバーに接続できませんでした");
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "生成の開始に失敗しました" }));
    showError("render-error", err.detail || "生成の開始に失敗しました");
    return;
  }

  showSection("progress-section");
  pollStatus();
}

async function pollStatus() {
  const res = await fetch(`/api/job/${state.jobId}/status`);
  const data = await res.json();

  if (data.state === "error") {
    showSection("edit-section");
    showError("render-error", data.error || "生成中にエラーが発生しました");
    return;
  }

  const bar = document.getElementById("progress-bar");
  const text = document.getElementById("progress-text");
  bar.max = data.total || 1;
  bar.value = data.current || 0;
  text.textContent = `${data.current} / ${data.total} ページ処理中`;

  if (data.state === "done") {
    showResult(data);
    return;
  }

  setTimeout(pollStatus, 500);
}

function showResult(status) {
  showSection("result-section");
  const list = document.getElementById("result-links");
  list.innerHTML = "";

  const addLink = (href, label) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    li.appendChild(a);
    list.appendChild(li);
  };

  addLink(`/api/job/${state.jobId}/result.pdf`, "サニタイズ済み PDF をダウンロード");
  if (status.hasMarkdown) addLink(`/api/job/${state.jobId}/result.md`, "Markdown をダウンロード");
  if (status.hasAudit) addLink(`/api/job/${state.jobId}/audit.json`, "監査レポートをダウンロード");
}

function resetToUpload() {
  state.jobId = null;
  state.pageCount = 0;
  state.pages = [];
  state.removedPages = new Set();
  state.boxes = new Map();
  document.getElementById("file-input").value = "";
  hideError("upload-error");
  hideError("render-error");
  showSection("upload-section");
}

// --- 初期化 ---

document.addEventListener("DOMContentLoaded", () => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) uploadFile(fileInput.files[0]);
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
  });

  document.getElementById("remove-range-input").addEventListener("input", (e) => {
    state.removedPages = parseRangeSpec(e.target.value);
    renderThumbnails();
  });

  document
    .getElementById("text-layer-select")
    .addEventListener("change", updateTextLayerDependentUI);
  updateTextLayerDependentUI();

  document.getElementById("generate-button").addEventListener("click", startGenerate);
  document.getElementById("restart-button").addEventListener("click", resetToUpload);
  document.getElementById("box-editor-close-button").addEventListener("click", closeBoxEditor);

  setupDrawLayer();
  showSection("upload-section");
});
