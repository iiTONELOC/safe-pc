from collections.abc import Callable


def reach_consensus(
    values: list[str],
    min_required: int = 2,
    num_required: Callable[[int], int] = lambda n: n - 1,
) -> str:
    """
    Determines if a consensus value can be reached from a list of string values.
    Args:
        values (list[str]): List of string values to consider for consensus.
        min_required (int, optional): Minimum number of matching values required for consensus. Defaults to 2.
        num_required (Callable[[int], int], optional): Function to determine the required number of matches based on the number of non-empty values. Defaults to lambda n: n - 1.
    Returns:
        str: The consensus value if the required number of matches is met; otherwise, an empty string.
    """
    # Filter out empty values
    filtered = [v for v in values if v and v.strip() != ""]
    n = len(filtered)
    if n == 0:
        return ""
    # require n-1 matches, minimum of 2
    required = max(min_required, num_required(n))
    counts: dict[str, int] = {}
    for v in filtered:
        counts[v] = counts.get(v, 0) + 1
    winner, votes = max(counts.items(), key=lambda kv: kv[1], default=("", 0))
    return winner if votes >= required else ""
