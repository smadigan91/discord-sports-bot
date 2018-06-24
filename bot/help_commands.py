help_map = {
    "/blurb [first_name: str]* [last_name: str]*": "Fetches the most recent blurb for a given player",
    "/last [num_days: int]* [player_search: str]*": "Fetches the last [num_days] worth of stats for a given player",
    "/log [player_search: str]*": "Fetches the most recent gamelog for a given player",
    "/season [year: int] [player_search: str]*": "fetches current season's (unless otherwise specified) stats for a "
                                                 "given player",
    "/highlight [player_search: str]* [index: int]": "Fetches the most recent highlight (or highlight at index if "
                                                     "specified) for a given player",
    "/highlight index [player_search: str]*": "Lists the last 10 highlights and their index number for a given player"
}  # commands to descriptions, * designating required


def get_help_text():
    body = ""
    for command, desc in help_map:
        body += f"{command}: {desc}" + "\n"
    return body
