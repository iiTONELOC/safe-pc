from os import path
from math import log2
from collections import Counter


def shannon_entropy(data: bytes) -> float:
    """Calculate the Shannon entropy of a byte sequence.

    Args:
        data (bytes): The byte sequence to analyze.

    Returns:
        float: The Shannon entropy value.

    Note: Uses the formula: H(X) = - Σ (p(x) * log2(p(x))) or
        H(X) = p(x1)(hx1) + p(x2)(hx2) + ... + p(xn)(hxn)
    """
    if not data:
        return 0.0

    # Count the frequency of each byte in the data
    byte_counts = Counter(data)
    total_bytes = len(data)

    # Calculate the entropy
    # The weighted averages of the possibilities for each byte value
    #
    entropy = -sum(
        (count / total_bytes) * log2(count / total_bytes)
        for count in byte_counts.values()
    )
    return entropy


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


def file_entropy(file_path: str) -> float:
    """Calculate the Shannon entropy of a file's contents.

    Args:
        file_path (str): The path to the file.

    Returns:
        float: The Shannon entropy value of the file's contents.
    """
    if not path.isfile(file_path):
        raise FileNotFoundError(f"No such file: '{file_path}'")

    with open(file_path, "rb") as f:
        data = f.read()

    return shannon_entropy(data)


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


def is_high_shannon_entropy(data: bytes, threshold: float = 7.5) -> bool:
    """Check if the byte sequence meets a specified Shannon entropy threshold.

    Args:
        data (bytes): The byte sequence to evaluate.
        threshold (float): The minimum Shannon entropy required.

    Returns:
        bool: True if the data's Shannon entropy is above the threshold, False otherwise.
    """
    entropy = shannon_entropy(data)
    return entropy >= threshold
