export const show = (el) => {
  el.classList.remove("hidden");
  el.classList.add("flex");
};

export const hide = (el) => {
  el.classList.add("hidden");
  el.classList.remove("flex");
};

export const disableSubmitButton = (submitBtn) => {
  submitBtn.disabled = true;
  submitBtn.classList.remove("cursor-pointer");
  submitBtn.classList.add("opacity-50", "cursor-not-allowed", "_disabled");
};

export const enableSubmitButton = (submitBtn) => {
  submitBtn.disabled = false;
  submitBtn.classList.remove("opacity-50", "cursor-not-allowed", "_disabled");
  submitBtn.classList.add("cursor-pointer");
};
