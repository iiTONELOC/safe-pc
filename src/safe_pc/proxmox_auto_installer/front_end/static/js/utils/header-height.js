document.addEventListener("DOMContentLoaded", function () {
  // Set a CSS variable for header height to use in layout calculations
  function updateHeaderHeight() {
    const header = document.getElementById("header");
    if (header) {
      document.documentElement.style.setProperty(
        "--header-height",
        `${header.offsetHeight}px`
      );
    }
  }

  window.addEventListener("load", updateHeaderHeight);
  window.addEventListener("resize", updateHeaderHeight);
  updateHeaderHeight();
});
