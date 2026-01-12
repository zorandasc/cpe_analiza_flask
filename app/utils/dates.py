from datetime import date, timedelta


# A business week that runs from Saturday 00:00 → Friday 23:59
# vraca datum petka za svaku sedmicu
# If today is Monday (weekday=0): (4-0) % 7 = 4 → add 4 days → Friday
# If today is Friday (weekday=4): (4-4) % 7 = 0 → add 0 days → today (Friday)
# If today is Saturday (weekday=5): (4-5) % 7 = -1 % 7 = 6 → add 6 days → next Friday
def get_current_week_friday(today=None):
    today = today or date.today()
    # Friday = 4
    return today + timedelta(days=(4 - today.weekday()) % 7)


# MAYBE YOU DON NEED THIS SATURDAY
# CAN BE CALCULATED FORM FRIDAY, current_week_frida
def get_passed_saturday(today=None):
    today = today or date.today()
    # Friday = 4
    return today - timedelta(days=(2 + today.weekday()) % 7)


# return date of last day of current month
def get_current_month_end(today=None):
    # Take today
    today = today or date.today()

    # Move to first day of next month
    if today.month == 12:
        first_next_month = date(today.year + 1, 1, 1)
    else:
        # Jump to the first day of the next month
        first_next_month = date(today.year, today.month + 1, 1)

    # Subtract one day Step back one day → last day of current month
    return first_next_month - timedelta(days=1)
