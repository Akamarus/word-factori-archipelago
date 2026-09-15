"""Bounded constructive viability proof for finite-machine campaign page orders.

This is a layout filter, not an item placement algorithm: Archipelago still fills
the actual multiworld. Optional checks are deliberately unnecessary for the proof.
"""
from functools import lru_cache

from .quantities import PROGRESSIVE_ITEMS
from .quantity_logic import budgets_for_location


@lru_cache(maxsize=128)
def upgrade_path(records, *, max_states=10000):
    """Return a funded 29-upgrade witness, or None (including search exhaustion)."""
    if type(max_states) is not int or max_states<0:
        raise ValueError('invalid quantity layout search bound')
    requirements=tuple(tuple(tuple(min(n,5) for n in b) for b in budgets_for_location(r)) for r in records)
    @lru_cache(maxsize=None)
    def reachable(tiers):
        total=0
        for start in range(0,len(requirements),6):
            count=sum(any(all(a>=b for a,b in zip(tiers,budget)) for budget in routes)
                      for routes in requirements[start:start+6])
            total+=count
            if count<4: break
        return total
    # The world reserves these two local early items for I and C.
    start=(1,0,0,0,0,0)
    if reachable(start)<2:
        return None
    start=(1,1,0,1,0,0)
    visited=set()
    def search(tiers):
        if tiers in visited or len(visited)>=max_states:
            return None
        visited.add(tiers)
        if tiers==(5,)*6:
            return () if reachable(tiers)==len(records) else None
        if reachable(tiers)<=sum(tiers)-1:
            return None
        choices=[]
        for family in range(6):
            if tiers[family]<5:
                nxt=tuple(n+(i==family) for i,n in enumerate(tiers))
                choices.append((family,nxt))
        # Larger immediate gains first; stable family order resolves ties.
        choices.sort(key=lambda choice:(-reachable(choice[1]),choice[0]))
        for family,nxt in choices:
            suffix=search(nxt)
            if suffix is not None:
                return (PROGRESSIVE_ITEMS[family],)+suffix
        return None
    suffix=search(start)
    return None if suffix is None else (PROGRESSIVE_ITEMS[3],PROGRESSIVE_ITEMS[1])+suffix
