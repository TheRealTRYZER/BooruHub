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
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
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

    def __contains__(self, item) -> bool:
        """Contains check (lock not needed under single-threaded asyncio)."""
        return item in self._data
