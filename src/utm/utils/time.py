from datetime import datetime


def get_current_tz_utc_off_hrs() -> int:
    """Get the current timezone offset in hours."""
    local_time = datetime.now().astimezone()
    offset_seconds = (
        local_time.utcoffset().total_seconds() if local_time.utcoffset() else 0  # type: ignore
    )
    return int(offset_seconds / 3600)
