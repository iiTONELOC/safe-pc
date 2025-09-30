from math import log2


def password_entropy(password: str) -> float:
    """Calculates the entropy of a password based on character variety and length.
    Passwords typically use the log2(pool_size^length) formula.
    https://www.okta.com/identity-101/password-entropy/

    Args:
        password (str): The password to evaluate.

    Returns:
        float: The calculated entropy of the password.
    """
    if not password:
        return 0.0

    # Define character sets
    char_sets = {
        "digits": set("0123456789"),
        "lowercase": set("abcdefghijklmnopqrstuvwxyz"),
        "uppercase": set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        "special": set("!@#$%^&*()-_=+[]{}|;:,.<>?/~`"),
    }

    # Determine which character sets are used in the password
    used_char_sets = [s for s in char_sets.values() if any(c in s for c in password)]
    pool_size = sum(len(s) for s in used_char_sets)

    # Calculate entropy
    entropy = log2(pool_size ** len(password)) if pool_size > 0 else 0.0
    return entropy


def is_high_entropy_password(password: str, threshold: float = 80.0) -> bool:
    """Check if a password meets a specified entropy threshold.

    Args:
        password (str): The password to evaluate.
        threshold (float): The minimum entropy required.

    Returns:
        bool: True if the password's entropy is above the threshold, False otherwise.
    """
    entropy = password_entropy(password)
    return entropy >= threshold
