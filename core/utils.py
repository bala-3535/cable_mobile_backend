from datetime import datetime, timedelta, timezone

def get_ist_now():
    """
    Returns the current time in Indian Standard Time (UTC+5:30).
    """
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))
