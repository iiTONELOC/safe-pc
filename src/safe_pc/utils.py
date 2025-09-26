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
