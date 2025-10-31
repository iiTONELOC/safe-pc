document.addEventListener("DOMContentLoaded", function () {
  const backButton = document.getElementById("back-button");

  if (window.history.length > 1) {
    backButton.classList.remove("hidden");
  } else {
    backButton.classList.add("hidden");
  }

  backButton.addEventListener("click", function () {
    window.history.back();
  });
});
