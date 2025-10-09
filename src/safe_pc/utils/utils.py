from os import getenv
from socket import gethostname, gethostbyname


def get_local_ip() -> str:
    """Gets the local IP address of the machine.

    Returns:
        str: The local IP address.
    """
    hostname = gethostname()
    local_ip = gethostbyname(hostname)
    return local_ip


def handle_keyboard_interrupt(func):
    """Decorator to handle KeyboardInterrupt exceptions gracefully.

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The wrapped function with KeyboardInterrupt handling.

    Usage:
    ```python
        @handle_keyboard_interrupt
        def main():
            # do some stuff
            print("Running...")
    ```
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print("Operation cancelled by user.")
            exit(0)

    return wrapper


def IS_TESTING() -> bool:
    """Check if the code is running in a testing environment.

    Returns:
        bool: True if running tests, False otherwise.
    """
    return getenv("CAPSTONE_TESTING", "0") == "1"


def IS_VERBOSE() -> bool:
    """Check if verbose mode is enabled via command-line arguments.

    Returns:
        bool: True if verbose mode is enabled, False otherwise.
    """
    return getenv("CAPSTONE_VERBOSE", "0") == "1"


def calculate_percentage(part: int, whole: int) -> float:
    """Calculate the percentage of `part` with respect to `whole`.

    Args:
        part (int): The part value.
        whole (int): The whole value.

    Returns:
        float: The calculated percentage. Returns 0.0 if `whole` is 0 to avoid division by zero.
    """
    if whole == 0:
        return 0.0
    return (part / whole) * 100.0
