IGNORED_INCLUDES = ["nullFlavor", "xmlns", "root", "width", "border"]


def filter_flattened_json(data: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    filters out pairs if the key includes substring that is in IGNORED_INCLUDES
    """
    new_data: list[dict[str, str]] = []
    for item in data:
        keys = item["path"].split(".")
        for k in IGNORED_INCLUDES:
            if k in keys:
                break
        else:
            new_data.append(item)

    return new_data
