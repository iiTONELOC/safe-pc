import { passwordHasEnoughEntropy } from "../utils/entropy.js";
import { disableSubmitButton, enableSubmitButton } from "../utils/dom.js";

export const validateFQDN = (fqdnElement, errorEl, formState) => {
  const fqdn = fqdnElement.value.trim();
  const fqdnRegex = /^(?=.{1,253}$)(?!-)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$/;

  if (fqdn.length === 0) {
    errorEl.textContent = "";
    formState.global.fqdn = null;
    return false;
  }

  if (!fqdnRegex.test(fqdn)) {
    errorEl.textContent = "Please enter a valid FQDN!";
    formState.global.fqdn = null;
    return false;
  } else {
    errorEl.textContent = "";
    formState.global.fqdn = fqdn;
    return true;
  }
};

export const passwordValidator = (
  passwordInput,
  passwordError,
  passwordConfirmError,
  passwordValidated,
  formState
) => {
  const value = passwordInput.value;
  if (value.length > 0 && value.length < 12) {
    passwordError.textContent = "Password must be at least 12 characters long.";
    passwordConfirmError.textContent = "";
    passwordValidated.isPasswordConfirmed = false;
    passwordValidated.isPasswordValid = false;
    formState.global["root-password-hashed"] = null;
  } else if (value.length >= 12 && !passwordHasEnoughEntropy(value)) {
    passwordError.textContent = "Low entropy password detected!";
    passwordConfirmError.textContent = "";
    passwordValidated.isPasswordConfirmed = false;
    passwordValidated.isPasswordValid = false;
    formState.global["root-password-hashed"] = null;
  } else if (value.length === 0) {
    passwordError.textContent = "";
    passwordValidated.isPasswordValid = false;
    formState.global["root-password-hashed"] = null;
  } else {
    passwordError.textContent = "";
    passwordValidated.isPasswordValid = true;
    formState.global["root-password-hashed"] = value;
  }
};

export const confirmPasswordValidator = (
  passwordInput,
  passwordConfirmInput,
  passwordConfirmError,
  passwordValidated,
  formState
) => {
  if (!passwordValidated.isPasswordValid) {
    passwordValidated.isPasswordConfirmed = false;
    formState.global["root-password-hashed"] = null;
    return;
  }
  if (passwordConfirmInput.value !== passwordInput.value) {
    passwordConfirmError.textContent = "Passwords do not match!";
    passwordValidated.isPasswordConfirmed = false;
    formState.global["root-password-hashed"] = null;
  } else {
    passwordConfirmError.textContent = "";
    passwordValidated.isPasswordConfirmed = true;
    formState.global["root-password-hashed"] = passwordInput.value;
  }
};

export const validateEmail = (emailElement, errorEl, formState) => {
  const email = emailElement.value.trim();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (email.length === 0) {
    errorEl.textContent = "";
    formState.global.email = null;
    return false;
  }
  if (!emailRegex.test(email) && email != "root@localhost") {
    errorEl.textContent = "Please enter a valid email address!";
    formState.global.email = null;
    return false;
  } else {
    errorEl.textContent = "";
    formState.global.email = email;
    return true;
  }
};

export const validateDns = (dnsElement, errorEl, formState) => {
  const dns = dnsElement.value.trim();
  const dnsRegex = /^(\d{1,3}\.){3}\d{1,3}(,\s*(\d{1,3}\.){3}\d{1,3})*$/;

  if (formState.network.source === "dhcp") {
    errorEl.textContent = "";
    formState.network.dns = null;
    return true;
  }
  if (dns.length === 0) {
    errorEl.textContent = "DNS cannot be empty!";
    formState.network.dns = null;
    return false;
  }
  if (!dnsRegex.test(dns)) {
    errorEl.textContent =
      "Please enter a valid DNS server IP or a comma separated list of IPs!";
    formState.network.dns = null;
    return false;
  } else {
    errorEl.textContent = "";
    formState.network.dns = dns;
    return true;
  }
};

export const validateCidr = (cidrElement, errorEl, formState) => {
  const cidr = cidrElement.value.trim();
  const cidrRegex = /^(?:\d{1,3}\.){3}\d{1,3}\/(?:\d|[1-2]\d|3[0-2])$/;

  if (formState.network.source === "dhcp") {
    errorEl.textContent = "";
    formState.network.cidr = null;
    return true;
  }
  if (cidr.length === 0) {
    errorEl.textContent = "CIDR cannot be empty!";
    formState.network.cidr = null;
    return false;
  }
  if (!cidrRegex.test(cidr)) {
    errorEl.textContent =
      "Please enter a valid CIDR notation (e.g., 192.168.1.238/24)!";
    formState.network.cidr = null;
    return false;
  } else {
    errorEl.textContent = "";
    formState.network.cidr = cidr;
    return true;
  }
};

export const validateGateway = (gatewayElement, errorEl, formState) => {
  const gateway = gatewayElement.value.trim();
  const ipRegex = /^(?:\d{1,3}\.){3}\d{1,3}$/;

  if (formState.network.source === "dhcp") {
    errorEl.textContent = "";
    formState.network.gateway = null;
    return true;
  }
  if (gateway.length === 0) {
    errorEl.textContent = "Gateway cannot be empty!";
    formState.network.gateway = null;
    return false;
  }
  if (!ipRegex.test(gateway)) {
    errorEl.textContent = "Please enter a valid Gateway IP address!";
    formState.network.gateway = null;
    return false;
  }

  // If CIDR is not present, assume /24
  if (!formState.network.cidr?.includes("/")) {
    formState.network.cidr = `${formState.network.cidr || gateway}/24`;
  }

  const [cidrIp, prefixLengthStr] = formState.network.cidr.split("/");
  const prefixLength = parseInt(prefixLengthStr, 10);

  if (isNaN(prefixLength) || prefixLength < 0 || prefixLength > 32) {
    errorEl.textContent = "Invalid CIDR configuration!";
    formState.network.gateway = null;
    return false;
  }

  // break the strings into its constituent octets and convert to integers
  const cidrParts = cidrIp.split(".").map((part) => parseInt(part, 10));
  const gatewayParts = gateway.split(".").map((part) => parseInt(part, 10));
  const mask = -1 << (32 - prefixLength);

  // shift the bits and combine to get the masked network address
  const cidrNetwork =
    (cidrParts[0] << 24) |
    (cidrParts[1] << 16) |
    (cidrParts[2] << 8) |
    cidrParts[3];
  const gatewayNetwork =
    (gatewayParts[0] << 24) |
    (gatewayParts[1] << 16) |
    (gatewayParts[2] << 8) |
    gatewayParts[3];

  // compare the masked network addresses
  if ((cidrNetwork & mask) !== (gatewayNetwork & mask)) {
    errorEl.textContent = "Gateway must be in the same subnet as the CIDR!";
    formState.network.gateway = null;
    return false;
  }

  formState.network.gateway = gateway;
  errorEl.textContent = "";
  return true;
};

export const handleSubmitBtnDisabledState = (submitBtn, passwordValidated) => {
  if (
    !passwordValidated.isPasswordValid ||
    !passwordValidated.isPasswordConfirmed
  ) {
    disableSubmitButton(submitBtn);
  } else {
    enableSubmitButton(submitBtn);
  }
};
