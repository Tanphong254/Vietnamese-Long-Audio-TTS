const form = document.getElementById("generate-form");
const contentBox = document.getElementById("content");
const voiceSelect = document.getElementById("voice");
const rateSelect = document.getElementById("rate");
const submitButton = document.getElementById("submit-button");
const submitLabel = document.getElementById("submit-label");
const formMessage = document.getElementById("form-message");
const historyList = document.getElementById("history-list");
const currentResult = document.getElementById("current-result");
const currentStatus = document.getElementById("current-status");

let jobs = [];
let newestLocalJobId = null;
let fetching = false;

const statusText = {
  queued: "Đang chờ",
  generating: "Đang tạo",
  completed: "Hoàn tất",
  failed: "Thất bại",
  idle: "Chưa tạo"
};

function formatDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(date);
}

function elapsedSeconds(job) {
  const start = job.created_at ? new Date(job.created_at).getTime() : Date.now();
  const end = job.status === "completed" || job.status === "failed"
    ? (job.completed_at ? new Date(job.completed_at).getTime() : Date.now())
    : Date.now();
  return Math.max(0, Math.floor((end - start) / 1000));
}

function formatElapsed(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

function statusClass(status) {
  if (status === "queued") return "queued";
  if (status === "generating") return "generating";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "idle";
}

function setStatus(node, status) {
  node.className = "status-pill " + statusClass(status);
  node.textContent = statusText[status] || statusText.idle;
}

function createAudio(job, compact) {
  const audio = document.createElement("audio");
  audio.className = "audio-player";
  audio.controls = true;
  audio.preload = "none";
  audio.src = "/api/jobs/" + job.id + "/audio";
  audio.setAttribute("aria-label", "Nghe AU " + job.id);
  const actions = document.createElement("div");
  actions.className = "action-row";
  const download = document.createElement("a");
  download.className = "small-button";
  download.href = "/api/jobs/" + job.id + "/audio?download=1";
  download.textContent = "↓ Tải AU " + job.id + ".mp3";
  actions.appendChild(download);
  if (!compact) {
    const open = document.createElement("a");
    open.className = "small-button";
    open.href = audio.src;
    open.target = "_blank";
    open.rel = "noopener";
    open.textContent = "↗ Mở audio";
    actions.appendChild(open);
  }
  const wrap = document.createElement("div");
  wrap.appendChild(audio);
  wrap.appendChild(actions);
  return wrap;
}

function renderCurrent(job) {
  if (!job) {
    setStatus(currentStatus, "idle");
    currentResult.className = "current-result empty";
    currentResult.replaceChildren();
    const icon = document.createElement("div");
    icon.className = "empty-icon";
    icon.textContent = "♫";
    const title = document.createElement("strong");
    title.textContent = "Audio sẽ hiện ở đây";
    const note = document.createElement("p");
    note.textContent = "Sau khi bạn bấm tạo, trạng thái và thời gian sẽ được cập nhật tại đây.";
    currentResult.append(icon, title, note);
    return;
  }

  setStatus(currentStatus, job.status);
  currentResult.className = "current-result";
  currentResult.replaceChildren();

  const top = document.createElement("div");
  top.className = "current-job-top";
  const symbol = document.createElement("div");
  symbol.className = "job-symbol";
  symbol.textContent = job.status === "completed" ? "✓" : job.status === "failed" ? "!" : "AU";
  const main = document.createElement("div");
  main.className = "job-main";
  const title = document.createElement("div");
  title.className = "job-title";
  title.textContent = job.label + " · " + statusText[job.status];
  const meta = document.createElement("div");
  meta.className = "job-meta";
  meta.textContent = job.voice_label + " · " + job.rate + "× · " + formatDate(job.created_at);
  main.append(title, meta);
  top.append(symbol, main);
  currentResult.appendChild(top);

  if (job.status === "queued" || job.status === "generating") {
    const timerRow = document.createElement("div");
    timerRow.className = "timer-row";
    const note = document.createElement("span");
    note.textContent = job.status === "queued" ? "Thời gian chờ + tạo" : "Thời gian đã chạy";
    const timer = document.createElement("span");
    timer.className = "timer";
    timer.dataset.jobId = String(job.id);
    timer.textContent = formatElapsed(elapsedSeconds(job));
    timerRow.append(note, timer);
    currentResult.appendChild(timerRow);
    const track = document.createElement("div");
    track.className = "progress-track";
    const bar = document.createElement("span");
    track.appendChild(bar);
    currentResult.appendChild(track);
    const detail = document.createElement("p");
    detail.className = "job-meta";
    detail.textContent = job.status === "queued"
      ? "Tác vụ sẽ bắt đầu khi lượt trước hoàn tất."
      : "Dịch vụ đang tổng hợp giọng nói. Không có phần trăm giả lập; đồng hồ vẫn chạy.";
    currentResult.appendChild(detail);
  } else if (job.status === "completed" && job.has_audio) {
    const done = document.createElement("p");
    done.className = "job-meta";
    done.textContent = "Audio đã sẵn sàng · hoàn tất lúc " + formatDate(job.completed_at);
    currentResult.append(done, createAudio(job, false));
  } else if (job.status === "failed") {
    const error = document.createElement("div");
    error.className = "error-box";
    error.textContent = job.error || "Không tạo được audio. Hãy xem chi tiết lượt chạy.";
    currentResult.appendChild(error);
  }
}

function renderHistory() {
  historyList.replaceChildren();
  if (jobs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "Chưa có lượt tạo audio nào.";
    historyList.appendChild(empty);
    return;
  }
  jobs.forEach((job) => {
    const item = document.createElement("article");
    item.className = "history-item";

    const head = document.createElement("div");
    head.className = "history-item-head";
    const left = document.createElement("div");
    left.className = "history-title";
    const badge = document.createElement("div");
    badge.className = "au-badge";
    badge.textContent = job.label;
    const copy = document.createElement("div");
    copy.className = "job-main";
    const title = document.createElement("div");
    title.className = "job-title";
    title.textContent = job.voice_label + " · " + job.rate + "×";
    const meta = document.createElement("div");
    meta.className = "job-meta";
    meta.textContent = formatDate(job.created_at);
    copy.append(title, meta);
    left.append(badge, copy);

    const pill = document.createElement("span");
    pill.className = "status-pill " + statusClass(job.status);
    pill.textContent = statusText[job.status] || job.status;
    head.append(left, pill);
    item.appendChild(head);

    if (job.status === "queued" || job.status === "generating") {
      const timerRow = document.createElement("div");
      timerRow.className = "timer-row";
      const label = document.createElement("span");
      label.textContent = job.status === "queued" ? "Đang đợi đến lượt" : "Đang khởi tạo";
      const timer = document.createElement("span");
      timer.className = "timer";
      timer.dataset.jobId = String(job.id);
      timer.textContent = formatElapsed(elapsedSeconds(job));
      timerRow.append(label, timer);
      item.appendChild(timerRow);
    } else if (job.status === "completed" && job.has_audio) {
      item.appendChild(createAudio(job, true));
    } else if (job.status === "failed") {
      const error = document.createElement("div");
      error.className = "history-error";
      error.textContent = job.error || "Tạo audio thất bại.";
      item.appendChild(error);
    }
    historyList.appendChild(item);
  });
}

async function refreshJobs() {
  if (fetching) return;
  fetching = true;
  try {
    const response = await fetch("/api/jobs?limit=80", { cache: "no-store" });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không tải được lịch sử.");
    const data = await response.json();
    jobs = data.jobs || [];
    const localJob = newestLocalJobId ? jobs.find((job) => job.id === newestLocalJobId) : null;
    const mostRecent = localJob || jobs[0] || null;
    renderCurrent(mostRecent);
    renderHistory();
  } catch (error) {
    formMessage.textContent = error.message || "Không kết nối được máy chủ.";
    formMessage.className = "form-message error";
  } finally {
    fetching = false;
  }
}

function updateCounts() {
  const text = contentBox.value;
  const trimmed = text.trim();
  const words = trimmed ? trimmed.split(/\s+/u).length : 0;
  document.getElementById("char-count").textContent = text.length.toLocaleString("vi-VN") + " ký tự";
  document.getElementById("word-count").textContent = words.toLocaleString("vi-VN") + " từ";
  const minutes = words ? Math.max(1, Math.round(words / (155 * Number(rateSelect.value)))) : 0;
  document.getElementById("time-estimate").textContent = words
    ? "Ước tính: khoảng " + minutes.toLocaleString("vi-VN") + " phút audio"
    : "Ước tính: —";
}

contentBox.addEventListener("input", updateCounts);
rateSelect.addEventListener("change", updateCounts);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = contentBox.value;
  if (!content.trim()) {
    formMessage.textContent = "Hãy nhập nội dung trước khi tạo audio.";
    formMessage.className = "form-message error";
    contentBox.focus();
    return;
  }

  submitButton.disabled = true;
  submitLabel.textContent = "Đang gửi yêu cầu…";
  formMessage.textContent = "Đang đăng ký lượt tạo audio...";
  formMessage.className = "form-message";

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content,
        voice: voiceSelect.value,
        rate: rateSelect.value
      })
    });
    const data = await response.json();
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error(data.error || "Không tạo được yêu cầu.");
    newestLocalJobId = data.job.id;
    formMessage.textContent = "Đã xếp hàng " + data.job.label + ". Số AU được giữ nguyên dù tác vụ thành công hay thất bại.";
    formMessage.className = "form-message";
    await refreshJobs();
  } catch (error) {
    formMessage.textContent = error.message || "Không gửi được yêu cầu.";
    formMessage.className = "form-message error";
  } finally {
    submitButton.disabled = false;
    submitLabel.textContent = "Tạo audio";
  }
});

document.getElementById("refresh-button").addEventListener("click", refreshJobs);

setInterval(() => {
  document.querySelectorAll(".timer[data-job-id]").forEach((node) => {
    const job = jobs.find((item) => String(item.id) === node.dataset.jobId);
    if (job) node.textContent = formatElapsed(elapsedSeconds(job));
  });
}, 1000);

updateCounts();
refreshJobs();
setInterval(refreshJobs, 2200);
