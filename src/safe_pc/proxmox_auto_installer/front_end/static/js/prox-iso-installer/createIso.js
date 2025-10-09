export async function createIso(
  formState,
  loadingSpinner,
  submitBtn,
  closeBtn,
  spinnerText,
  hide
) {
  const [{ showAlert }, { handleCreateIso }] = await Promise.all([
    import("../utils/alert.js"),
    import("../api.js"),
  ]);
  // submit the form
  const result = await handleCreateIso(formState).catch((error) => {
    console.error("Error creating ISO:", error);
    return { success: false, message: error.message || "Unknown error" };
  });

  if (!result?.status) {
    showAlert(result.error || "Error creating ISO");
    setTimeout(() => {
      hide(loadingSpinner);
      // re-enable the submit button
      submitBtn.disabled = false;
      closeBtn.click();
    }, 6800);
  } else {
    const { jobId } = result;
    console.log(`ISO creation started. Job ID: ${jobId}`);

    // open a socket connection to receive progress updates
    const socket = new WebSocket(`wss://${window.location.host}/api/ws/iso`);

    socket.onopen = () => {
      console.log("WebSocket connection established.");
      // change the loading spinner text
      socket.send(JSON.stringify({ jobId }));
      loadingSpinner.setAttribute("data-text", "Starting ISO creation...");
    };

    socket.onmessage = (event) => {
      const { data } = JSON.parse(event.data);
      console.log("Received data:", data);
      if (data.type === "progress") {
        const progress = data.progress || 0;
        spinnerText.textContent = `Progress: ${progress}%`;
      } else if (data.type === "status") {
        const status = data.status || "Starting...";
        spinnerText.textContent = `Status: ${status}`;
      } else if (data.type === "error") {
        const error = data.error || "Unknown error";
        spinnerText.textContent = `Error: ${error}`;
        showAlert(`Error during ISO creation: ${error}`);
      }
    };

    socket.onclose = (event) => {
      if (event.wasClean) {
        console.log(
          `WebSocket connection closed cleanly, code=${event.code} reason=${event.reason}`
        );
      } else {
        console.warn("WebSocket connection closed unexpectedly");
      }
      // change the loading spinner text
      loadingSpinner.setAttribute("data-text", "ISO creation complete.");
      spinnerText.textContent = "ISO creation process has finished.";
      setTimeout(() => {
        hide(loadingSpinner);
        // re-enable the submit button
        submitBtn.disabled = false;
        closeBtn.click();
      }, 1500);
    };

    socket.onerror = (error) => {
      console.error("WebSocket error:", error);
      showAlert("WebSocket error occurred. See console for details.");
      // change the loading spinner text
      loadingSpinner.setAttribute("data-text", "Error during ISO creation.");
      spinnerText.textContent = "ISO creation process has finished.";
      setTimeout(() => {
        hide(loadingSpinner);
        // re-enable the submit button
        submitBtn.disabled = false;
        closeBtn.click();
      }, 4500);
    };
  }
}
