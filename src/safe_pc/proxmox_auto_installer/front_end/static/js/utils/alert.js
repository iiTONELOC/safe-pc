export function showAlert(message, type = "error") {
  const alertBox = document.getElementById("form-alert");
  const alertMessage = alertBox.querySelector("#alert-message");
  alertMessage.textContent = message;
  alertBox.classList.remove("hidden");
  // Automatically hide the alert after 6.5 seconds
  setTimeout(() => {
    alertBox.classList.add("hidden");
  }, 6500);
}

export function hideAlert() {
  const alertBox = document.getElementById("form-alert");
  alertBox.classList.add("hidden");
}

export function updateAlertMessage(message) {
  const alertBox = document.getElementById("form-alert");
  const alertMessage = alertBox.querySelector(".alert-message");
  alertMessage.textContent = message;
}

// Initialize alert close button functionality
document.addEventListener("DOMContentLoaded", () => {
  const alertBox = document.getElementById("form-alert");
  const closeButton = alertBox.querySelector("button");
  closeButton.addEventListener("click", () => {
    alertBox.classList.add("hidden");
  });
});
