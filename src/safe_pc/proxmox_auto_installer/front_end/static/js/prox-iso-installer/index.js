import {
  validateDns,
  validateCidr,
  validateFQDN,
  validateEmail,
  validateGateway,
  passwordValidator,
  confirmPasswordValidator,
  handleSubmitBtnDisabledState,
} from "./validators.js";
import { fetchInstallerData, handleCreateIso } from "../api.js";

import { show, hide, disableSubmitButton } from "../utils/dom.js";
import { hashPassword } from "../utils/crypto.js";

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
  const loadingSpinner = document.getElementById("loading-spinner");

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

  // set default values from data attributes - these are hardcoded in the HTML and are not dynamic
  [cidr, gateway, dns, fqdnInput, emailInput].forEach((field) => {
    const defaultValue = field.getAttribute("data-default-value");
    if (defaultValue) {
      field.value = defaultValue;
    }
  });

  // Populate country select
  Object.entries(countries).forEach(([code, name]) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = code;

    if (name === currentCountry) {
      option.selected = true;
    }
    countrySelect.appendChild(option);
  });

  // Populate keyboard select
  keyboards.forEach((keyboard) => {
    const option = document.createElement("option");

    option.value = keyboard;
    option.textContent = keyboard.toUpperCase();
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
    // Email validation
    emailInput.addEventListener(event, () => {
      validateEmail(emailInput, emailError, formState);
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
    // Password validation
    passwordInput.addEventListener(event, (e) => {
      passwordValidator(
        passwordInput,
        passwordError,
        passwordConfirmError,
        passwordValidated,
        formState
      );
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
    // Confirm password validation
    passwordConfirmInput.addEventListener(event, (e) => {
      confirmPasswordValidator(
        passwordInput,
        passwordConfirmInput,
        passwordConfirmError,
        passwordValidated,
        formState
      );
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
    // DNS validation
    dns.addEventListener(event, () => {
      validateDns(dns, dnsError, formState, sourceSelect);
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
    // CIDR validation
    cidr.addEventListener(event, () => {
      validateCidr(cidr, cidrError, formState, sourceSelect);
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
    // Gateway validation
    gateway.addEventListener(event, () => {
      validateGateway(gateway, gatewayError, formState, sourceSelect);
      handleSubmitBtnDisabledState(submitBtn, passwordValidated);
    });
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

  // ensure submit button is correctly enabled/disabled on load
  handleSubmitBtnDisabledState(submitBtn, passwordValidated);

  // open modal
  btn.addEventListener("click", () => show(modal));

  // close modal
  closeBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    hide(modal);
    // set the passwords back to empty
    passwordInput.value = "";
    passwordConfirmInput.value = "";
    formState.global.rootPassword = null;
    passwordValidated.isPasswordValid = false;
    passwordValidated.isPasswordConfirmed = false;
  });

  // prevent clicks inside modal-content from closing
  content.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // handle form submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (
      !passwordValidated.isPasswordValid ||
      !passwordValidated.isPasswordConfirmed
    ) {
      return;
    }

    // disable the submit button to prevent multiple clicks
    disableSubmitButton(submitBtn);
    // display loading spinner
    show(loadingSpinner);

    const result = await handleCreateIso(formState);
    //TODO: handle errors - currently this api isn't expected to fail as its not implemented yet
    // hide the spinner
    hide(loadingSpinner);
    // re-enable the submit button
    submitBtn.disabled = false;
    closeBtn.click();
  });
});
