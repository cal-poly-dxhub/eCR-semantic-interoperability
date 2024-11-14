from typing import Dict

IGNORED_INCLUDES = ["nullFlavor", "xmlns", "root", "width", "border"]


def filter_flattened_json(data: Dict[str, str]) -> Dict[str, str]:
    """
    filters out pairs if the key includes substring that is in IGNORED_INCLUDES
    """
    new_data: Dict[str, str] = {}
    for key in list(data.keys()):
        keys = key.split(".")
        for k in IGNORED_INCLUDES:
            if k in keys:
                break
        else:
            new_data[key] = data[key]

    return new_data
