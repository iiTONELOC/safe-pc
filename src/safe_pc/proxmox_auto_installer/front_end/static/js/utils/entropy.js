export const passwordHasEnoughEntropy = (password) => {
  if (!password || password.length < 12) return false; // minimum length check

  const charSets = {
    digits: [/\d/, 10], // 0-9
    lowercase: [/[a-z]/, 26], // a-z
    uppercase: [/[A-Z]/, 26], // A-Z
    special: [/[!@#$%^&*(),.?":{}|<>]/, 20], // special chars
  };

  let poolSize = 0;
  for (const [_, [regex, size]] of Object.entries(charSets)) {
    if (regex.test(password)) {
      poolSize += size;
    }
  }

  const entropy = password.length * Math.log2(poolSize);

  return entropy > 80;
};
