import {
  validateDns,
  validateCidr,
  validateFQDN,
  validateEmail,
  validateGateway,
  passwordValidator,
  confirmPasswordValidator,
} from "./validators.js";
import { show, hide } from "../utils/dom.js";
import { fetchInstallerData } from "../api.js";

const passwordValidated = {
  isPasswordValid: false,
  isPasswordConfirmed: false,
};

const formState = {
  global: {
    fqdn: null,
    email: null,
    country: null,
    timezone: null,
    rootPassword: null,
    keyboardLayout: null,
  },
  network: {
    dns: null,
    cidr: null,
    source: null,
    gateway: null,
  },
};

document.addEventListener("DOMContentLoaded", async function () {
  const { installerSettings } = await fetchInstallerData();
  const { countries, keyboards, timezones, currentCountry, currentTimezone } =
    installerSettings;

  // general elements

  const btn = document.getElementById("create-iso-btn");
  const submitBtn = document.getElementById("submit-btn");
  const modal = document.getElementById("create-iso-modal");
  const content = modal.querySelector(".modal-content");
  const form = document.getElementById("proxmox-settings-form");
  const closeBtn = document.getElementById("close-create-iso-modal");

  //input fields
  const fqdnInput = document.getElementById("fqdn");
  const emailInput = document.getElementById("mailto");
  const passwordInput = document.getElementById("root-password");
  const passwordConfirmInput = document.getElementById("confirm-password");

  // error spans
  const fqdnError = document.getElementById("fqdn-error");
  const emailError = document.getElementById("mailto-error");
  const passwordError = document.getElementById("password-error");
  const passwordConfirmError = document.getElementById(
    "password-confirm-error"
  );
  const dnsError = document.getElementById("dns-error");
  const cidrError = document.getElementById("cidr-error");
  const gatewayError = document.getElementById("gateway-error");

  // selects
  const countrySelect = document.getElementById("country");
  const keyboardSelect = document.getElementById("keyboard");
  const timezoneSelect = document.getElementById("timezone");
  // network fields
  const dns = document.getElementById("dns");
  const cidr = document.getElementById("cidr");
  const gateway = document.getElementById("gateway");
  const sourceSelect = document.getElementById("source");

  // set default values from data attributes
  [cidr, gateway, dns, fqdnInput, emailInput].forEach((field) => {
    const defaultValue = field.getAttribute("data-default-value");
    if (defaultValue) {
      field.value = defaultValue;
    }
  });

  // Initialize formState with default values
  formState.network.source = sourceSelect.value;
  formState.network.cidr = cidr.value || null;
  formState.network.gateway = gateway.value || null;
  formState.network.dns = dns.value || null;
  formState.global.fqdn = fqdnInput.value || null;
  formState.global.email = emailInput.value || null;
  formState.global.country = countrySelect.value || null;
  formState.global.timezone = timezoneSelect.value || null;
  formState.global.keyboardLayout = keyboardSelect.value || null;
  formState.global.rootPassword = null;

  // event listeners for validation
  for (const event of ["input", "change"]) {
    // FQDN validation
    fqdnInput.addEventListener(event, () =>
      validateFQDN(fqdnInput, fqdnError, formState)
    );
    // Password validation
    passwordInput.addEventListener(event, () =>
      passwordValidator({
        formState,
        passwordInput,
        passwordError,
        passwordValidated,
        passwordConfirmError,
      })
    );
    // Password confirmation
    passwordConfirmInput.addEventListener(event, () =>
      confirmPasswordValidator({
        formState,
        passwordInput,
        passwordValidated,
        passwordConfirmInput,
        passwordConfirmError,
      })
    );
    // Email validation
    emailInput.addEventListener(event, () =>
      validateEmail(emailInput, emailError, formState)
    );
    // DNS validation
    dns.addEventListener(event, () =>
      validateDns(dns, dnsError, formState, sourceSelect)
    );
    // CIDR validation
    cidr.addEventListener(event, () =>
      validateCidr(cidr, cidrError, formState, sourceSelect)
    );
    // Gateway validation
    gateway.addEventListener(event, () =>
      validateGateway(gateway, gatewayError, formState, sourceSelect)
    );
  }

  if (
    !passwordValidated.isPasswordValid ||
    !passwordValidated.isPasswordConfirmed
  ) {
    // disable the submit button
    submitBtn.disabled = true;
    submitBtn.classList.remove("cursor-pointer");
    submitBtn.classList.add("opacity-50", "cursor-not-allowed", "_disabled");
  } else {
    submitBtn.disabled = false;
    submitBtn.classList.remove("opacity-50", "cursor-not-allowed", "_disabled");
    submitBtn.classList.add("cursor-pointer");
  }

  // watch for changes to source select
  sourceSelect.addEventListener("change", (_) => {
    const required = sourceSelect.value === "from-answer";

    [cidr, gateway, dns].forEach((field) => {
      field.required = required;

      const label = field.previousElementSibling;
      const asterisk = label.querySelector("span");

      if (required) {
        asterisk.classList.remove("hidden");

        const defaultValue = field.getAttribute("data-default-value");

        if (defaultValue) {
          field.value = defaultValue;
        }
      } else {
        asterisk.classList.add("hidden");
        field.value = "";
      }
    });
  });

  // Populate country select
  Object.entries(countries).forEach(([code, name]) => {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = name;

    if (name === currentCountry) {
      option.selected = true;
    }
    countrySelect.appendChild(option);
  });

  // Populate keyboard select
  keyboards.forEach((keyboard) => {
    const option = document.createElement("option");

    option.value = keyboard;
    option.textContent = keyboard;
    keyboardSelect.appendChild(option);

    // Normalize both values for comparison
    const normalizedKeyboard = keyboard.trim().toLowerCase();
    const normalizedNavigatorLang = navigator.language.trim().toLowerCase();

    if (normalizedKeyboard === normalizedNavigatorLang) {
      option.selected = true;
    }
  });

  // Populate timezone select
  timezones.forEach((tz) => {
    const option = document.createElement("option");
    option.value = tz;
    option.textContent = tz;
    if (tz === currentTimezone) {
      option.selected = true;
    }
    timezoneSelect.appendChild(option);
  });

  // open modal
  btn.addEventListener("click", () => show(modal));
  // // close on backdrop click
  // modal.addEventListener("click", () => hide(modal));
  // close on cancel button
  closeBtn.addEventListener("click", () => hide(modal));

  // prevent clicks inside modal-content from closing
  content.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // handle form submit
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (
      !passwordValidated.isPasswordValid ||
      !passwordValidated.isPasswordConfirmed
    ) {
      return;
    }

    // TODO: Form should be valid here
    // disable the submit button to prevent multiple clicks
    // display loading spinner
    // submit the form data to the backend to start ISO creation process
  });
});
