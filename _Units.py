from typing import Any


class UnitType(type):
    def __new__(self, name, base, dict):
        pass
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass