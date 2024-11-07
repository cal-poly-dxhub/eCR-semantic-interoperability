from typing import Any, Dict, List, Tuple


def flatten_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    takes in a nested dictionary and returns a flattened dictionary
    e.g. {"a": {"b": 1}} -> {"a.b": 1}
    Handles arrays by including the index in the key
    e.g. {"a": [{"b": 1}, {"c": 2}]} -> {"a.0.b": 1, "a.1.c": 2}
    """

    def flatten_json_helper(data: Any, parent_key: str = "") -> Dict[str, Any]:
        items: List[Tuple[str, Any]] = []
        if isinstance(data, dict):
            for key, value in data.items():  # type: ignore
                new_key = f"{parent_key}.{key}" if parent_key else key  # type: ignore
                items.extend(flatten_json_helper(value, new_key).items())  # type: ignore
        elif isinstance(data, list):
            for index, value in enumerate(data):  # type: ignore
                new_key = f"{parent_key}.{index}" if parent_key else str(index)
                items.extend(flatten_json_helper(value, new_key).items())
        else:
            items.append((parent_key, data))
        return dict(items)

    return flatten_json_helper(data)
