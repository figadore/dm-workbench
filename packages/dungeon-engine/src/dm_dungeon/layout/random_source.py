"""One explicit deterministic random source for layout generation."""

import hashlib
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class DeterministicRandom:
    """SHA-256 counter stream with deterministic selection and shuffling."""

    def __init__(self, seed: int, generator_version: str) -> None:
        self._key = f"{generator_version}\x1f{seed}".encode()
        self._counter = 0

    @property
    def draw_count(self) -> int:
        """Number of random words consumed so far."""
        return self._counter

    def randbelow(self, upper_bound: int) -> int:
        """Return a deterministic integer in ``range(upper_bound)``."""
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        counter = self._counter.to_bytes(16, byteorder="big", signed=False)
        self._counter += 1
        value = int.from_bytes(
            hashlib.sha256(self._key + counter).digest(),
            byteorder="big",
            signed=False,
        )
        return value % upper_bound

    def choice(self, values: Sequence[T]) -> T:
        """Choose one item from a non-empty stable sequence."""
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self.randbelow(len(values))]

    def shuffle(self, values: list[T]) -> None:
        """Shuffle a list in place using deterministic Fisher-Yates draws."""
        for index in range(len(values) - 1, 0, -1):
            other = self.randbelow(index + 1)
            values[index], values[other] = values[other], values[index]
