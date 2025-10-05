from os import getenv


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


def handle_keyboard_interrupt_async(func):
    """Decorator to handle KeyboardInterrupt exceptions gracefully in async functions.

    Args:
        func (callable): The async function to be decorated.

    Returns:
        callable: The wrapped async function with KeyboardInterrupt handling.

    Usage:
    ```python
        @handle_keyboard_interrupt_async
        async def main():
            # do some stuff
            print("Running...")
    ```
    """

    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
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
