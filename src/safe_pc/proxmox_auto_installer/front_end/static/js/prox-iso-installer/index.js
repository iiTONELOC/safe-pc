import {
  populateTzSelect,
  populateCountrySelect,
  populateKeyboardSelect,
} from "./helpers.js";
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
import { createIso } from "./createIso.js";
import { fetchInstallerData } from "../api.js";
import { formElements } from "./formElements.js";
import { formState, passwordValidated } from "./formState.js";
import { show, hide, disableSubmitButton } from "../utils/dom.js";

// start fetching installer data immediately don't wait for DOMContentLoaded
const installerData = fetchInstallerData().catch((error) => {
  console.error("Error fetching installer data:", error);
  return { installerSettings: {} };
});

// wait for the DOM to be ready
document.addEventListener("DOMContentLoaded", async () => {
  // wait for installer data to be fetched
  const { installerSettings } = await installerData;
  const { countries, keyboards, timezones, currentCountry, currentTimezone } =
    installerSettings;

  // get the form elements
  const {
    dns,
    cidr,
    form,
    modal,
    content,
    gateway,
    closeBtn,
    dnsError,
    cidrError,
    fqdnError,
    fqdnInput,
    submitBtn,
    emailInput,
    emailError,
    spinnerText,
    createIsoBtn,
    sourceSelect,
    gatewayError,
    passwordError,
    passwordInput,
    countrySelect,
    keyboardSelect,
    timezoneSelect,
    loadingSpinner,
    passwordConfirmInput,
    passwordConfirmError,
  } = formElements();

  // set default values from data attributes - these are hardcoded in the HTML
  [cidr, gateway, dns, fqdnInput, emailInput].forEach((field) => {
    const defaultValue = field.getAttribute("data-default-value");
    if (defaultValue) {
      field.value = defaultValue;
    }
  });

  // populate the selects using the fetched data
  populateKeyboardSelect(keyboards, keyboardSelect);
  populateTzSelect(timezones, timezoneSelect, currentTimezone);
  populateCountrySelect(countries, countrySelect, currentCountry);

  // Initialize formState with default values
  formState.network.dns = dns.value || null;
  formState.network.cidr = cidr.value || null;
  formState.network.source = sourceSelect.value;
  formState.network.gateway = gateway.value || null;
  formState.global["root-password-hashed"] = null;
  formState.global.fqdn = fqdnInput.value || null;
  formState.global.email = emailInput.value || null;
  formState.global.country = countrySelect.value || null;
  formState.global.timezone = timezoneSelect.value || null;
  formState.global.keyboard = keyboardSelect.value || null;

  // attach event listeners to form elements to handle validation and state updates
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

  // watch for changes to source select - enable/disable relevant fields
  sourceSelect.addEventListener("change", (_) => {
    // fields are only needed if sourcing from answer file
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
  createIsoBtn.addEventListener("click", () => show(modal));

  // close modal
  closeBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    hide(modal);
    // set the passwords back to empty
    passwordInput.value = "";
    passwordConfirmInput.value = "";
    formState.global["root-password-hashed"] = null;
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

    await createIso(
      formState,
      loadingSpinner,
      submitBtn,
      closeBtn,
      spinnerText,
      hide
    );
  });
});
