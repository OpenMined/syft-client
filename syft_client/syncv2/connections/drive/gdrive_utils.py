from typing import Any, List


def listify(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    else:
        return [obj]
