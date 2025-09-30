document.addEventListener("DOMContentLoaded", function () {
  // currently just toggles the modal
  const btn = document.getElementById("create-iso-btn");
  const modal = document.getElementById("create-iso-modal");
  btn.addEventListener("click", () => {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  });
  modal.addEventListener("click", () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  });
});
