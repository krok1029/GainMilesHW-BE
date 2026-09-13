from typing import Any, NoReturn

from flask.json.provider import DefaultJSONProvider


def reject_non_json_constant(value: str) -> NoReturn:
    raise ValueError(f"Invalid JSON constant: {value}")


class StrictJSONProvider(DefaultJSONProvider):
    def loads(self, s: str | bytes, **kwargs: Any) -> Any:
        # Python's decoder otherwise accepts NaN and Infinity outside JSON syntax.
        kwargs["parse_constant"] = reject_non_json_constant
        return super().loads(s, **kwargs)
