export const populateCountrySelect = (
  countries,
  selectElement,
  currentCountry
) => {
  Object.entries(countries).forEach(([code, name]) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = code;
    if (name === currentCountry) {
      option.selected = true;
    }
    selectElement.appendChild(option);
  });
};

export const populateKeyboardSelect = (keyboards, selectElement) => {
  keyboards.forEach((keyboard) => {
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
  });
};

export const populateTzSelect = (timezones, selectElement, currentTimezone) => {
  timezones.forEach((tz) => {
    const option = document.createElement("option");
    option.value = tz;
    option.textContent = tz;
    if (tz === currentTimezone) {
      option.selected = true;
    }
    selectElement.appendChild(option);
  });
};
