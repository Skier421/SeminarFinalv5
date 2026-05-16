"""
Hardcoded historical headlines for classroom use.
At least one major event per decade from 1920 to 2020.
"""

# Date-specific headlines for precise historical accuracy
HEADLINES_BY_DATE = {
    '1945-08-15': 'World War II ends after Allied victory in Europe and the Pacific.',
}

# Check if in practice mode
try:
    from practice_mode import PRACTICE_MODE
    if PRACTICE_MODE:
        from practice_data import PRACTICE_HEADLINES, get_practice_headline_for_year
        HEADLINES_BY_YEAR = PRACTICE_HEADLINES
    else:
        HEADLINES_BY_YEAR = {
            1929: "Wall Street crashes, triggering the Great Depression.",
            1930: "Stocks keep tumbling as the U.S. economy struggles with the Great Depression.",
            1931: "Unemployment rises sharply as banks fail across the country.",
            1932: "Franklin D. Roosevelt wins the presidency amid economic turmoil.",
            1933: "New Deal programs launch to stabilize the economy and support workers.",
            1934: "Financial reforms create the SEC and strengthen investor protections.",
            1935: "Social Security Act signed into law to aid retirees and unemployed workers.",
            1936: "Economic growth returns slowly as recovery policies continue.",
            1937: "A recession returns as production slows and unemployment spikes again.",
            1938: "Recovery resumes after corrective fiscal action and banking stabilization.",
            1939: "World War II begins with Germany's invasion of Poland.",
            1940: "Europe is engulfed in war while U.S. industry ramps up production.",
            1941: "The attack on Pearl Harbor draws America into World War II.",
            1942: "War production surges as the U.S. mobilizes for the global conflict.",
            1943: "Allied forces gain momentum across multiple fronts.",
            1944: "D-Day invasion marks a turning point in the war against Nazi Germany.",
            1957: "Soviet Union launches Sputnik, marking the start of the Space Age.",
            1969: "Apollo 11 lands on the Moon and humans walk on its surface.",
            1973: "Oil embargo shocks global markets and accelerates inflation.",
            1989: "The Berlin Wall falls, signaling a major Cold War turning point.",
            1991: "The Soviet Union dissolves, reshaping global politics.",
            2001: "September 11 attacks transform global security policy.",
            2008: "Global financial crisis deepens after major banking failures.",
            2020: "COVID-19 pandemic disrupts economies and daily life worldwide."
        }
except ImportError:
    HEADLINES_BY_YEAR = {
        1929: "Wall Street crashes, triggering the Great Depression.",
        1930: "Stocks keep tumbling as the U.S. economy struggles with the Great Depression.",
        1931: "Unemployment rises sharply as banks fail across the country.",
        1932: "Franklin D. Roosevelt wins the presidency amid economic turmoil.",
        1933: "New Deal programs launch to stabilize the economy and support workers.",
        1934: "Financial reforms create the SEC and strengthen investor protections.",
        1935: "Social Security Act signed into law to aid retirees and unemployed workers.",
        1936: "Economic growth returns slowly as recovery policies continue.",
        1937: "A recession returns as production slows and unemployment spikes again.",
        1938: "Recovery resumes after corrective fiscal action and banking stabilization.",
        1939: "World War II begins with Germany's invasion of Poland.",
        1940: "Europe is engulfed in war while U.S. industry ramps up production.",
        1941: "The attack on Pearl Harbor draws America into World War II.",
        1942: "War production surges as the U.S. mobilizes for the global conflict.",
        1943: "Allied forces gain momentum across multiple fronts.",
        1944: "D-Day invasion marks a turning point in the war against Nazi Germany.",
        1957: "Soviet Union launches Sputnik, marking the start of the Space Age.",
        1969: "Apollo 11 lands on the Moon and humans walk on its surface.",
        1973: "Oil embargo shocks global markets and accelerates inflation.",
        1989: "The Berlin Wall falls, signaling a major Cold War turning point.",
        1991: "The Soviet Union dissolves, reshaping global politics.",
        2001: "September 11 attacks transform global security policy.",
        2008: "Global financial crisis deepens after major banking failures.",
        2020: "COVID-19 pandemic disrupts economies and daily life worldwide."
    }


def get_headline_for_date(date_str: str) -> str:
    """Return headline for a specific date if available, otherwise None."""
    if date_str in HEADLINES_BY_DATE:
        return HEADLINES_BY_DATE[date_str]
    return None


# Sentiment mapping for insider rumors: buy = bullish, sell = bearish
HEADLINE_SENTIMENT = {
    1929: 'sell', 1930: 'sell', 1931: 'sell',
    1932: 'buy',  1933: 'buy',  1934: 'buy',  1935: 'buy',  1936: 'buy',
    1937: 'sell', 1938: 'buy',
    1939: 'sell', 1940: 'sell', 1941: 'sell',
    1942: 'buy',  1943: 'buy',  1944: 'buy',
    1957: 'buy',
    1969: 'buy',
    1973: 'sell',
    1989: 'buy',
    1991: 'buy',
    2001: 'sell',
    2008: 'sell',
    2020: 'sell',
}


def get_headline_sentiment(year: int) -> str:
    """Return buy/sell sentiment for a year, with nearest-year fallback."""
    if year in HEADLINE_SENTIMENT:
        return HEADLINE_SENTIMENT[year]
    available_years = sorted(HEADLINE_SENTIMENT.keys())
    nearest_year = None
    for y in available_years:
        if y <= year:
            nearest_year = y
        else:
            break
    if nearest_year is not None:
        return HEADLINE_SENTIMENT[nearest_year]
    return 'buy'


def get_headline_for_year(year: int) -> str:
    """Return the best available headline for a given year."""
    if year in HEADLINES_BY_YEAR:
        return HEADLINES_BY_YEAR[year]

    # Prefer the closest year before the current date.
    available_years = sorted(HEADLINES_BY_YEAR.keys())
    nearest_year = None
    for y in available_years:
        if y <= year:
            nearest_year = y
        else:
            break

    if nearest_year is not None:
        return HEADLINES_BY_YEAR[nearest_year]

    # Fallback to the earliest known headline
    return HEADLINES_BY_YEAR.get(available_years[0], 'Historical headline unavailable.')
