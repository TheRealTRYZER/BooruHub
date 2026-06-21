import pytest
from app.core.bounded_set import BoundedSet


@pytest.mark.asyncio
async def test_bounded_set():
    bset = BoundedSet(maxsize=3)
    
    # Add new items
    added = await bset.add_many([1, 2])
    assert added == [1, 2]
    assert 1 in bset
    assert 2 in bset
    assert 3 not in bset
    
    # Try adding duplicates
    added = await bset.add_many([2, 3])
    assert added == [3]
    
    # Eviction should keep the most recent elements up to maxsize (B-L5)
    added = await bset.add_many([4, 5, 6, 7])
    assert len(added) == 4
    assert 1 not in bset
    assert 4 not in bset
    assert 5 in bset
    assert 6 in bset
    assert 7 in bset
