document.addEventListener("DOMContentLoaded", () => {
  const card = document.getElementById("download-card");
  if (!card) return;
  const jobId = card.dataset.jobId;
  const deleteBtn = document.getElementById("delete-iso-btn");
  const statusText = document.getElementById("status-text");

  if (!jobId || !deleteBtn || !statusText) return;

  deleteBtn.addEventListener("click", async () => {
    try {
      deleteBtn.disabled = true;
      const original = deleteBtn.textContent;
      deleteBtn.textContent = "Deleting...";

      const res = await fetch(`/api/delete-iso/${jobId}`);
      if (res.ok) {
        statusText.textContent = "ISO deleted. Redirecting...";
        statusText.classList.remove("hidden");
        setTimeout(() => (window.location.href = "/"), 1200);
      } else {
        statusText.textContent = "Error deleting ISO.";
        statusText.classList.remove("hidden");
        deleteBtn.disabled = false;
        deleteBtn.textContent = original;
      }
    } catch {
      statusText.textContent = "Network error.";
      statusText.classList.remove("hidden");
      deleteBtn.disabled = false;
      deleteBtn.textContent = "Delete ISO";
    }
  });
});
