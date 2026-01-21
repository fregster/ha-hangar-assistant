"""Pure-Python shim for the `lru` module used by some packages.

This implements a minimal LRU mapping compatible with the small surface
area used in tests. It's intentionally simple and optimized for clarity,
not raw performance.
"""
from collections import OrderedDict
from typing import Any, Optional


class LRU(OrderedDict):
    """A minimal LRU mapping with an optional maxsize.

    Usage:
        cache = LRU(maxsize=128)
        cache[key] = value
    """

    def __init__(self, maxsize: Optional[int] = 128, *args, **kwargs):
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: Any, value: Any) -> None:
        if key in self:
            # move to the end (most-recently used)
            OrderedDict.__delitem__(self, key)
        OrderedDict.__setitem__(self, key, value)
        if self.maxsize is not None:
            while len(self) > self.maxsize:
                self.popitem(last=False)


# Provide a compatibility alias used by some callers
LRUDict = LRU

# Minimal convenience factory to mimic C-extension constructors
def lrudict(maxsize: Optional[int] = 128, *args, **kwargs) -> LRU:
    return LRU(maxsize=maxsize, *args, **kwargs)
