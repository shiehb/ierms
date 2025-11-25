def getQuarterDates(quarter, year):
    """
    Get the start and end dates for a given quarter and year
    """
    quarters = {
        1: {'start': f'{year}-01-01', 'end': f'{year}-03-31'},
        2: {'start': f'{year}-04-01', 'end': f'{year}-06-30'},
        3: {'start': f'{year}-07-01', 'end': f'{year}-09-30'},
        4: {'start': f'{year}-10-01', 'end': f'{year}-12-31'}
    }
    return quarters.get(quarter, quarters[1])


# Alias for consistent naming
get_quarter_dates = getQuarterDates