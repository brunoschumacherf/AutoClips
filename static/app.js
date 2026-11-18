const progressPanel = document.querySelector("#progress[data-refresh]");
if (progressPanel) {
  let socket;
  let refreshing = false;
  const timer = window.setInterval(updateProgress, 3500);

  async function updateProgress() {
    const progress = document.querySelector("#progress[data-refresh]");
    if (!progress) {
      window.clearInterval(timer);
      if (socket) socket.close();
      return;
    }
    if (refreshing) return;
    refreshing = true;
    try {
      const response = await fetch(progress.dataset.refresh, {
        credentials: "same-origin",
      });
      if (response.ok && !response.redirected) {
        const fragment = new DOMParser().parseFromString(
          await response.text(),
          "text/html",
        );
        const updated = fragment.querySelector("#progress");
        if (updated) progress.replaceWith(updated);
      }
    } catch {
      // The next poll can recover from a temporary connection failure.
    } finally {
      refreshing = false;
    }
  }

  if (window.WebSocket) {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(
      scheme + "//" + location.host + progressPanel.dataset.socket,
    );
    socket.addEventListener("message", updateProgress);
  }
}

const original = document.querySelector("#original");
const timeline = document.querySelector("#timeline");
if (original && timeline) {
  timeline.addEventListener("input", () => {
    original.currentTime = Number(timeline.value);
  });
  original.addEventListener("timeupdate", () => {
    timeline.value = original.currentTime;
  });
  document.querySelectorAll("[data-mark]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector("#id_" + button.dataset.mark).value = Number(
        timeline.value,
      ).toFixed(2);
    });
  });
}
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
