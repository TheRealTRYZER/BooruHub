"""Thread-safe bounded set with automatic eviction using OrderedDict and asyncio.Lock."""
import asyncio
from collections import OrderedDict
from typing import List, Optional


class BoundedSet:
    """Thread-safe bounded set with automatic eviction using OrderedDict and asyncio.Lock."""
    __slots__ = ("_data", "_max", "_lock")

    def __init__(self, maxsize: int = 10000) -> None:
        self._data: OrderedDict = OrderedDict()
        self._max = maxsize
        self._lock: Optional[asyncio.Lock] = None

    async def add_many(self, items) -> List:
        """Add items, returning only those that were new."""
        async with self._lock_ctx():
            new = []
            for item in items:
                if item not in self._data:
                    new.append(item)
                    self._data[item] = True
                    self._data.move_to_end(item)

            # Bounded eviction of oldest elements (B-L5)
            while len(self._data) > self._max:
                self._data.popitem(last=False)
            return new

    async def peek_new(self, items) -> List:
        """Return which items are new without recording them.

        Lets a caller persist the items first and only then mark them as seen,
        so a failed write does not permanently suppress the item.
        """
        async with self._lock_ctx():
            return [item for item in items if item not in self._data]

    def _lock_ctx(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def __contains__(self, item) -> bool:
        """Contains check (lock not needed under single-threaded asyncio)."""
        return item in self._data
