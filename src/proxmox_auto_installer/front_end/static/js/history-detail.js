let answerFileText = "";

document.addEventListener("DOMContentLoaded", () => {
  const loadBtn = document.getElementById("load-answer-btn");
  const downloadBtn = document.getElementById("download-answer-btn");
  const deleteBtn = document.getElementById("delete-job-btn");

  const modal = document.getElementById("delete-confirm-modal");
  const cancelDeleteBtn = document.getElementById("cancel-delete-btn");
  const confirmDeleteBtn = document.getElementById("confirm-delete-btn");

  /* Load Answer File */
  loadBtn.addEventListener("click", async () => {
    loadBtn.disabled = true;
    loadBtn.innerText = "Loading...";

    try {
      const res = await fetch(`/api/answer-file/${loadBtn.dataset.jobId}`);
      const text = await res.text();

      answerFileText = text;

      const pre = document.getElementById("answer-file");
      pre.textContent = text;
      pre.classList.remove("hidden");

      downloadBtn.classList.remove("hidden");

      loadBtn.innerText = "Loaded ✓";
    } catch {
      loadBtn.innerText = "Error";
    }
  });

  /* Download Answer File */
  downloadBtn.addEventListener("click", () => {
    const blob = new Blob([answerFileText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `answer-file-${loadBtn.dataset.jobId}.toml`;
    a.click();

    URL.revokeObjectURL(url);
  });

  /* Open Delete Modal */
  deleteBtn.addEventListener("click", () => {
    modal.classList.remove("hidden");
  });

  /* Cancel Delete */
  cancelDeleteBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  /* Confirm Delete */
  confirmDeleteBtn.addEventListener("click", async () => {
    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.innerText = "Deleting...";

    const jobId = confirmDeleteBtn.dataset.jobId;

    try {
      const res = await fetch(`/api/delete-iso/${jobId}`, { method: "DELETE" });

      if (res.ok) {
        confirmDeleteBtn.innerText = "Deleted Successfully ✓";
        setTimeout(() => {
          window.location.href = "/";
        }, 800);
      } else {
        throw new Error();
      }
    } catch {
      confirmDeleteBtn.innerText = "Error";
      setTimeout(() => {
        modal.classList.add("hidden");
        confirmDeleteBtn.innerText = "Yes, Delete It";
        confirmDeleteBtn.disabled = false;
      }, 1200);
    }
  });
});
