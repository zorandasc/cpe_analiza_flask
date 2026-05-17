from datetime import date, timedelta

# determine the current week's Monday, and build everything from there.
def get_current_week_bounds(today=None):
    """
    Returns the strict Monday-to-Sunday bounds and the Friday stamp
    for the ISO week containing 'today'.
    """
    today = today or date.today()

    # .weekday() returns 0 for Monday, 6 for Sunday
    # This gives us the Monday of the current week
    current_monday = today - timedelta(days=today.weekday())

    current_friday = current_monday + timedelta(days=4)

    current_sunday = current_monday + timedelta(days=6)

    return {
        "monday": current_monday,
        "friday": current_friday,
        "sunday": current_sunday,
    }


# return date of last day of current month
def get_current_month_end(today=None):
    # Take today
    today = today or date.today()

    # Move to first day of next month
    if today.month == 12:
        # today year+1, firt month, first day
        first_next_month = date(today.year + 1, 1, 1)
    else:
        # Jump to the first day of the next month
        first_next_month = date(today.year, today.month + 1, 1)

    # Subtract one day Step back one day → last day of current month
    return first_next_month - timedelta(days=1)


def get_previous_month_end(today=None):
    today = today or date.today()

    # Find the first day of the CURRENT month
    first_day_current_month = date(today.year, today.month, 1)

    # Step back one day -> results in the last day of the PREVIOUS month
    return first_day_current_month - timedelta(days=1)
