const elementMap = () => [
  {
    id: "create-iso-btn",
    varName: "createIsoBtn",
    element: document.getElementById("create-iso-btn"),
  },
  {
    id: "submit-btn",
    varName: "submitBtn",
    element: document.getElementById("submit-btn"),
  },
  {
    id: "create-iso-modal",
    varName: "modal",
    element: document.getElementById("create-iso-modal"),
  },
  {
    id: null,
    varName: "content",
    element: document
      .getElementById("create-iso-modal")
      .querySelector(".modal-content"),
  },
  {
    id: "proxmox-settings-form",
    varName: "form",
    element: document.getElementById("proxmox-settings-form"),
  },
  {
    id: "close-create-iso-modal",
    varName: "closeBtn",
    element: document.getElementById("close-create-iso-modal"),
  },
  {
    id: "loading-spinner",
    varName: "loadingSpinner",
    element: document.getElementById("loading-spinner"),
  },
  {
    id: "fqdn",
    varName: "fqdnInput",
    element: document.getElementById("fqdn"),
  },
  {
    id: "mailto",
    varName: "emailInput",
    element: document.getElementById("mailto"),
  },
  {
    id: "root-password",
    varName: "passwordInput",
    element: document.getElementById("root-password"),
  },
  {
    id: "confirm-password",
    varName: "passwordConfirmInput",
    element: document.getElementById("confirm-password"),
  },
  {
    id: "fqdn-error",
    varName: "fqdnError",
    element: document.getElementById("fqdn-error"),
  },
  {
    id: "mailto-error",
    varName: "emailError",
    element: document.getElementById("mailto-error"),
  },
  {
    id: "password-error",
    varName: "passwordError",
    element: document.getElementById("password-error"),
  },
  {
    id: "password-confirm-error",
    varName: "passwordConfirmError",
    element: document.getElementById("password-confirm-error"),
  },
  {
    id: "dns-error",
    varName: "dnsError",
    element: document.getElementById("dns-error"),
  },
  {
    id: "cidr-error",
    varName: "cidrError",
    element: document.getElementById("cidr-error"),
  },
  {
    id: "gateway-error",
    varName: "gatewayError",
    element: document.getElementById("gateway-error"),
  },
  {
    id: "country",
    varName: "countrySelect",
    element: document.getElementById("country"),
  },
  {
    id: "keyboard",
    varName: "keyboardSelect",
    element: document.getElementById("keyboard"),
  },
  {
    id: "timezone",
    varName: "timezoneSelect",
    element: document.getElementById("timezone"),
  },
  { id: "dns", varName: "dns", element: document.getElementById("dns") },
  { id: "cidr", varName: "cidr", element: document.getElementById("cidr") },
  {
    id: "gateway",
    varName: "gateway",
    element: document.getElementById("gateway"),
  },
  {
    id: "source",
    varName: "sourceSelect",
    element: document.getElementById("source"),
  },
  {
    id: "spinner-status",
    varName: "spinnerStatus",
    element: document.getElementById("spinner-status"),
  },
  {
    id: "spinner-progress",
    varName: "spinnerProgress",
    element: document.getElementById("spinner-progress"),
  },
  {
    id: "spinner-message",
    varName: "spinnerMessage",
    element: document.getElementById("spinner-message"),
  },
  {
    id: "spinner-bar",
    varName: "spinnerBar",
    element: document.getElementById("spinner-bar"),
  },
  {
    id: "spinner-bar-fill",
    varName: "spinnerBarFill",
    element: document.getElementById("spinner-bar-fill"),
  },
  {
    id: "spinner-complete",
    varName: "spinnerComplete",
    element: document.getElementById("spinner-complete"),
  },
];

const formElements = () => {
  const formElements = {};
  for (const { varName, element } of elementMap()) {
    formElements[varName] = element;
  }

  return formElements;
};

export { formElements };
