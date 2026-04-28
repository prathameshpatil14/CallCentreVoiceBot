import json
import importlib
import importlib.util
from typing import Any


_ORJSON_SPEC = importlib.util.find_spec("orjson")
_ORJSON = importlib.import_module("orjson") if _ORJSON_SPEC else None


def dumps(payload: Any) -> str:
    if _ORJSON is not None:
        return _ORJSON.dumps(payload).decode("utf-8")
    return json.dumps(payload, ensure_ascii=False)


def dumpb(payload: Any) -> bytes:
    if _ORJSON is not None:
        return _ORJSON.dumps(payload)
    return json.dumps(payload).encode("utf-8")


def loads(raw: str | bytes) -> Any:
    if _ORJSON is not None:
        return _ORJSON.loads(raw)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)
