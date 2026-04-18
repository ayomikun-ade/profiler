import os
import time
from uuid import UUID

try:
    from uuid import uuid7 as _stdlib_uuid7  # type: ignore[attr-defined]

    def uuid7() -> UUID:
        return _stdlib_uuid7()

except ImportError:

    def uuid7() -> UUID:
        timestamp_ms = int(time.time() * 1000)
        ts_bytes = timestamp_ms.to_bytes(6, "big")
        rand = bytearray(os.urandom(10))
        rand[0] = (rand[0] & 0x0F) | 0x70
        rand[2] = (rand[2] & 0x3F) | 0x80
        return UUID(bytes=bytes(ts_bytes) + bytes(rand))
