export async function createIso(
  formState,
  loadingSpinner,
  submitBtn,
  closeBtn,
  hide
) {
  const [{ showAlert }, { handleCreateIso }, { capitalizeWords }] =
    await Promise.all([
      import("../utils/alert.js"),
      import("../api.js"),
      import("./helpers.js"),
    ]);

  const spinnerStatus = document.getElementById("spinner-status");
  const spinnerProgress = document.getElementById("spinner-progress");
  const spinnerMessage = document.getElementById("spinner-message");

  /**
   * Handle WebSocket messages from the server.
   */
  const handleSocketMessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const data = payload.data || {};

      switch (data.type) {
        case "progress": {
          const progress = data.progress ?? 0;

          // Text update
          spinnerProgress.textContent = `${progress}%`;

          // Bar elements
          const bar = document.getElementById("spinner-bar");
          const fill = document.getElementById("spinner-bar-fill");
          const completeIcon = document.getElementById("spinner-complete");

          if (bar && fill) {
            bar.classList.remove("hidden");
            fill.style.width = `${progress}%`;
          }

          if (data.status)
            spinnerStatus.textContent = capitalizeWords(data.status);
          if (data.message) spinnerMessage.textContent = data.message;

          // If done, show checkmark - not quite finished
          // process is over when socket closes
          if (progress >= 100) {
            setTimeout(() => {
              completeIcon.classList.remove("hidden");
            }, 300);
          } else if (
            progress < 100 &&
            !completeIcon.classList.contains("hidden")
          ) {
            completeIcon.classList.add("hidden");
          }

          break;
        }

        case "status":
          spinnerStatus.textContent = `Status: ${data.status || "Starting..."}`;
          break;

        case "error": {
          const error = data.message || data.error || "Unknown error";
          spinnerStatus.textContent = "Status: Error";
          spinnerMessage.textContent = error;
          spinnerProgress.textContent = "";
          showAlert(`Error during ISO creation: ${error}`);
          break;
        }

        default:
          console.warn("Unknown WebSocket message type:", data);
      }
    } catch (err) {
      console.error("Failed to parse WebSocket message:", err, event.data);
    }
  };

  /**
   * Handle WebSocket closure.
   */
  const handleSocketClose = (event, jobId) => {
    if (event.wasClean) {
      console.log(
        `WebSocket closed cleanly, code=${event.code} reason=${event.reason}`
      );
    } else {
      console.warn("WebSocket closed unexpectedly");
    }

    spinnerMessage.textContent = "ISO creation process has finished.";

    setTimeout(() => {
      hide(loadingSpinner);
      submitBtn.disabled = false;
      closeBtn.click();
      // Redirect to download page
      window.location.href = `iso-download/${jobId}`;
    }, 250);
  };

  /**
   * Handle WebSocket errors.
   */
  const handleSocketError = (error) => {
    console.error("WebSocket error:", error);
    showAlert("WebSocket error occurred. See console for details.");
    spinnerMessage.textContent = "Error during ISO creation.";
    setTimeout(() => {
      hide(loadingSpinner);
      submitBtn.disabled = false;
      closeBtn.click();
    }, 4500);
  };

  /**
   * Open WebSocket and register handlers.
   */
  const openSocket = (jobId) => {
    const socket = new WebSocket(`wss://${window.location.host}/api/ws/iso`);

    socket.onopen = () => {
      console.log("WebSocket connection established.");
      socket.send(JSON.stringify({ jobId }));
      console.log("Sent jobId to server:", jobId);
      spinnerMessage.textContent = "Starting ISO creation...";
    };

    socket.onmessage = handleSocketMessage;
    socket.onclose = (event) => handleSocketClose(event, jobId);
    socket.onerror = handleSocketError;
  };

  // ---- Execute the ISO creation request ----
  try {
    const result = await handleCreateIso(formState);
    // register the custom event listener for when the ISO creation finishes

    const { jobId } = result;
    if (!result?.status) {
      showAlert(result.error || "Error creating ISO");
      setTimeout(() => {
        hide(loadingSpinner);
        submitBtn.disabled = false;
        closeBtn.click();
        window.location.href = `iso-download/${jobId}`;
      }, 6800);
      return;
    }

    openSocket(jobId);
  } catch (error) {
    console.error("Error creating ISO:", error);
    showAlert(error.message || "Unknown error");
    setTimeout(() => {
      hide(loadingSpinner);
      submitBtn.disabled = false;
      closeBtn.click();
    }, 6800);
  }
}
