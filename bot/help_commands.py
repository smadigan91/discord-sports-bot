help_map = {
    "**/blurb [first_name: str]`*` [last_name: str]`*`**": "\nFetches the most recent blurb for a given player\n",

    "**/last [num_days: int]`*` [player_search: str]`*`**": "\nFetches the last [num_days] worth of stats for a given "
                                                            "player",

    "**/log [player_search: str]`*`**": "Fetches the most recent gamelog for a given player\n",

    "**/season [year: int] [player_search: str]`*`**": "\nfetches current season's (unless otherwise specified) stats "
                                                       "for a given player\n",

    "**/highlight [player_search: str]`*` [index: int]**": "\nFetches the most recent highlight (or highlight at index "
                                                           "if specified) for a given player\n",

    "**/highlight index [player_search: str]`*`**": "\nLists the last 10 highlights and their index number for a given "
                                                    "player\n"
}  # commands to descriptions, * designating required


def get_help_text():
    body = ""
    for command, desc in help_map.items():
        body += f"{command}: {desc}" + "\n"
    return body
