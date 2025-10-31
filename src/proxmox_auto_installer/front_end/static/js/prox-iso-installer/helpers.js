export const populateCountrySelect = (
  countries,
  selectElement,
  currentCountry
) => {
  for (const [code, name] of Object.entries(countries)) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = code;
    if (name === currentCountry) {
      option.selected = true;
    }
    selectElement.appendChild(option);
  }
};

export const populateKeyboardSelect = (keyboards, selectElement) => {
  for (const keyboard of keyboards) {
    const option = document.createElement("option");
    option.value = keyboard;
    option.textContent = keyboard.toUpperCase();
    selectElement.appendChild(option);
    // Normalize both values for comparison
    const normalizedKeyboard = keyboard.trim().toLowerCase();
    const normalizedNavigatorLang = navigator.language.trim().toLowerCase();
    if (normalizedKeyboard === normalizedNavigatorLang) {
      option.selected = true;
    }
  }
};

export const populateTzSelect = (timezones, selectElement, currentTimezone) => {
  for (const tz of timezones) {
    const option = document.createElement("option");
    option.value = tz;
    option.textContent = tz;
    if (tz === currentTimezone) {
      option.selected = true;
    }
    selectElement.appendChild(option);
  }
};

export const capitalizeWords = (str) => {
  if (typeof str !== "string") return "";
  return str
    .trim()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};
