import re
from typing import Any


def json_to_str(data: list[dict[str, Any]]) -> list[str]:
    """
    convert JSON data to a list of strings for vectorization, keeping data in the same object together
    """

    return table_to_str(data)

    # def sanitize_string(s: str) -> str:
    #     # Remove or replace not allowed characters
    #     return re.sub(r"[^\w\s]", "", s)

    # vectorizable: list[str] = []
    # for item in data:
    #     item_strs: list[str] = []
    #     for _, value in item.items():
    #         if isinstance(value, dict):
    #             item_strs.extend(json_to_str([value]))
    #         elif isinstance(value, list):
    #             item_strs.extend(json_to_str(value))  # type: ignore
    #         else:
    #             item_strs.append(sanitize_string(str(value)))
    #     vectorizable.append(" ".join(item_strs))

    # return vectorizable


def get_text_segments(data: list[dict[str, Any]]) -> list[str]:
    """
    get "text" segments from data
    """
    text_segments: list[str] = []
    for item in data:
        for key, value in item.items():
            if key == "text":
                text_segments.append(value)
            elif isinstance(value, dict):
                text_segments.extend(get_text_segments([value]))
            elif isinstance(value, list):
                text_segments.extend(get_text_segments(value))  # type: ignore

    return text_segments


def table_to_str(data: list[dict[str, Any]]) -> list[str]:
    """
    extract information out of tables in data
    """

    vectorizable: list[str] = []

    for item in data:
        for key, value in item.items():
            if key == "table":
                # tables have tr, td, and th tags
                # put all of them in a string separated by spaces
                # look for th dict and add those to the string (the start)
                # find all other td tags and add those to the string
                table_str = ""
                for row in value:
                    for cell in row:
                        if isinstance(cell, dict):
                            table_str += " ".join(cell.values()) + " "
                        elif isinstance(cell, str):
                            table_str += cell + " "
                vectorizable.append(table_str)

            elif isinstance(value, dict):
                vectorizable.extend(table_to_str([value]))
            elif isinstance(value, list):
                vectorizable.extend(table_to_str(value))  # type: ignore

    return vectorizable
