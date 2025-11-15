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

const getTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

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
    spinnerBar,
    createIsoBtn,
    sourceSelect,
    gatewayError,
    passwordError,
    passwordInput,
    countrySelect,
    keyboardSelect,
    timezoneSelect,
    loadingSpinner,
    spinnerStatus,
    spinnerBarFill,
    spinnerComplete,
    spinnerProgress,
    spinnerMessage,
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
  //  check the source to see if we need to set network values
  const isFromAnswerFile = sourceSelect.value === "from-answer";

  if (isFromAnswerFile) {
    formState.network.cidr = cidr.value || null;
    formState.network.gateway = gateway.value || null;
    formState.network.dns = dns.value || null;
  } else {
    formState.network.cidr = null;
    formState.network.gateway = null;
    formState.network.dns = null;
  }

  formState.network.source = sourceSelect.value;
  formState.global["root-password-hashed"] = null;
  formState.global.fqdn = fqdnInput.value || null;
  formState.global.email = emailInput.value || null;
  formState.global.country = countrySelect.value || null;
  formState.global.timezone = timezoneSelect.value || null;
  formState.global.keyboard = keyboardSelect.value || null;

  // set the timezone select to the user's timezone if no currentTimezone is or does not match
  if (
    !currentTimezone ||
    currentTimezone.toLowerCase() !== getTimeZone().toLowerCase()
  ) {
    const userTz = getTimeZone();
    timezoneSelect.value = userTz;
    formState.global.timezone = userTz;
  }

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

  // handle changes for the keyboard, country, and timezone selects
  [keyboardSelect, countrySelect, timezoneSelect].forEach((select) => {
    select.addEventListener("change", () => {
      formState.global[select.name] = select.value || null;
    });
  });

  const handleSourceChange = () => {
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
  };

  handleSourceChange();
  // watch for changes to source select - enable/disable relevant fields
  sourceSelect.addEventListener("change", (_) => {
    // fields are only needed if sourcing from answer file
    handleSourceChange();
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

    // Reset spinner UI before new job
    spinnerBar.classList.add("hidden");
    spinnerBarFill.style.width = "0%";
    spinnerComplete.classList.add("hidden");
    spinnerProgress.textContent = "";
    spinnerMessage.textContent = "";
    spinnerStatus.textContent = "Processing...";

    // display loading spinner
    show(loadingSpinner);
    //ensure the country is lowercase
    if (formState.global.country) {
      formState.global.country = formState.global.country.toLowerCase();
    }

    await createIso(formState, loadingSpinner, submitBtn, closeBtn, hide);
  });
});
