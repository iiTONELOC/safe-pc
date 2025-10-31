document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-job-id]");
    if (!btn) return;

    const jobId = btn.dataset.jobId;
    window.location.href = `/history/${jobId}`;
  });
});
