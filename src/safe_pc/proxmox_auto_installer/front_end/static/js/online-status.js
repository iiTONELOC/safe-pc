document.addEventListener("DOMContentLoaded", () => {
  const onlineBox = document.getElementById("status-online");
  const offlineBox = document.getElementById("status-offline");

  function update() {
    if (navigator.onLine) {
      onlineBox.classList.remove("hidden");
      offlineBox.classList.add("hidden");
    } else {
      onlineBox.classList.add("hidden");
      offlineBox.classList.remove("hidden");
    }
  }

  update();
  window.addEventListener("online", update);
  window.addEventListener("offline", update);
});
