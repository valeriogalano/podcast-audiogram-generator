"""Pure selection parsers for episodes and soundbites.

These functions avoid side effects and are designed for unit testing.
"""
from __future__ import annotations
from typing import List


def parse_episode_selection(value, max_episode: int) -> List[int]:
    """Parse episode selection: single int, comma list, 'all'/'a', or 'last'.

    Returns a list of episode numbers (1-based). Raises ``ValueError`` for
    invalid inputs or out-of-range values.
    """
    if value is None:
        return []
    if isinstance(value, int):
        if 1 <= value <= max_episode:
            return [value]
        raise ValueError('Episode number out of range')
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('all', 'a'):
            return list(range(1, max_episode + 1))
        if v == 'last':
            return [max_episode]
        parts = [p.strip() for p in v.split(',') if p.strip()]
        nums: List[int] = []
        for p in parts:
            if not p.isdigit():
                raise ValueError('Non-numeric value in the list')
            n = int(p)
            if not (1 <= n <= max_episode):
                raise ValueError('Episode number out of range')
            if n not in nums:
                nums.append(n)
        if not nums:
            raise ValueError('No valid episodes specified')
        return nums
    raise ValueError('Unsupported episode format')


def parse_soundbite_selection(value, max_soundbites: int) -> List[int]:
    """Parse soundbite selection (single int, list, 'all') to list of ints."""
    if value is None:
        return list(range(1, max_soundbites + 1))
    if isinstance(value, int):
        if 1 <= value <= max_soundbites:
            return [value]
        raise ValueError('Soundbite number out of range')
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('all', 'a'):
            return list(range(1, max_soundbites + 1))
        parts = [p.strip() for p in v.split(',') if p.strip()]
        nums: List[int] = []
        for p in parts:
            if not p.isdigit():
                raise ValueError('Non-numeric value in the list')
            n = int(p)
            if not (1 <= n <= max_soundbites):
                raise ValueError('Soundbite number out of range')
            if n not in nums:
                nums.append(n)
        if not nums:
            raise ValueError('No valid soundbites specified')
        return nums
    raise ValueError('Unsupported soundbite format')
