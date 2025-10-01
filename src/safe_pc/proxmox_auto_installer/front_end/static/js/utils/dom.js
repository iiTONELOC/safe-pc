export const show = (el) => {
  el.classList.remove("hidden");
  el.classList.add("flex");
};

export const hide = (el) => {
  el.classList.add("hidden");
  el.classList.remove("flex");
};
