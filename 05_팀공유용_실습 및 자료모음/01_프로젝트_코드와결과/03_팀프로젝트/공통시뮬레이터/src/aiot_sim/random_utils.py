import hashlib
import random


def rng(seed: int, *keys: object) -> random.Random:
    """Stable independent streams, unaffected by room iteration order."""
    digest = hashlib.sha256(
        (str(seed) + "|" + "|".join(map(str, keys))).encode()
    ).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))
