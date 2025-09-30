document.addEventListener("DOMContentLoaded", () => {
  const ws = new WebSocket(`wss://${window.location.hostname}:33008/reload-ws`);

  ws.onmessage = (event) => {
    console.log(`Message from server: ${event.data}`);
    if (event.data === "reload") {
      console.log("Update received!\nReloading browser...");
      location.reload();
    }
  };
});
