"""Record ids: 24 lowercase hex characters, time-ordered (4-byte seconds + 5 random bytes + 3-byte counter).
The same shape the API and the frontend already use, without depending on MongoDB's bson package."""
import itertools
import os
import re
import threading
import time

_HEX24 = re.compile(r"^[0-9a-f]{24}$")
_counter = itertools.count(int.from_bytes(os.urandom(3), "big"))
_lock = threading.Lock()
_RAND = os.urandom(5).hex()


class InvalidId(ValueError):
    pass


class ObjectId(str):
    """A str subclass, so ids compare equal to their string form and serialize as plain strings."""

    def __new__(cls, value=None):
        if value is None:
            with _lock:
                n = next(_counter) & 0xFFFFFF
            value = f"{int(time.time()) & 0xFFFFFFFF:08x}{_RAND}{n:06x}"
        value = str(value).lower()
        if not _HEX24.match(value):
            raise InvalidId(f"{value!r} is not a valid id")
        return super().__new__(cls, value)

    @staticmethod
    def is_valid(value) -> bool:
        return bool(_HEX24.match(str(value).lower()))
