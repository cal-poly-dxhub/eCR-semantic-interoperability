from typing import Any
from uuid import uuid4


def flatten_json(data: dict[str, Any]) -> list[dict[str, str]]:
    """
    takes in a nested dictionary and returns a list of dictionaries with 'key' and 'value'
    e.g. {"a": {"b": 1}} -> [{"path": "a.b", "value": 1}]
    Handles arrays by including the index in the key
    e.g. {"a": [{"b": 1}, {"c": 2}]} -> [{"path": "a.0.b", "value": 1}, {"path": "a.1.c", "value": 2}]
    also removes ".content" from keys
    """

    def flatten_json_helper(data: Any, parent_key: str = "") -> list[dict[str, str]]:
        items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for key, value in data.items():  # type: ignore
                new_key = f"{parent_key}.{key}" if parent_key else key  # type: ignore
                new_key = new_key.replace(".content", "")  # type: ignore
                items.extend(flatten_json_helper(value, new_key))  # type: ignore
        elif isinstance(data, list):
            for index, value in enumerate(data):  # type: ignore
                new_key = f"{parent_key}.{index}" if parent_key else str(index)
                new_key = new_key.replace(".content", "")
                items.extend(flatten_json_helper(value, new_key))
        else:
            items.append(
                {
                    "path": parent_key.replace(".content", ""),
                    "value": data,
                    "id": str(uuid4()),
                }
            )

        return items

    return flatten_json_helper(data)
