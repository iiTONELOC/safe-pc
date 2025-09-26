document.addEventListener("DOMContentLoaded", () => {
  const ws = new WebSocket(`ws://${window.location.hostname}:3308/reload-ws`);
  ws.onmessage = (event) => {
    if (event.data === "reload") {
      console.log("Update received!\nReloading browser...");
      location.reload();
    }
  };
});
