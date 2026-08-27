"""Order-independent deterministic pseudo-random helper."""

import hashlib
import random


class DeterministicSeedService:
    """Derive independent deterministic streams from a persisted master seed."""

    def __init__(self, master_seed):
        self.master_seed = str(master_seed)

    def _digest(self, namespace):
        payload = f"{self.master_seed}|{namespace}".encode("utf-8")
        return hashlib.sha256(payload).digest()

    def stable_int(self, namespace, modulo=None):
        value = int.from_bytes(self._digest(namespace), "big")
        if modulo is None:
            return value
        if modulo <= 0:
            raise ValueError("modulo must be greater than zero")
        return value % modulo

    def rng(self, namespace):
        return random.Random(self.stable_int(namespace))

    def choice(self, namespace, values):
        values = tuple(values)
        if not values:
            raise ValueError("values must not be empty")
        return values[self.stable_int(namespace, len(values))]

    def token(self, namespace, length=12):
        if length <= 0:
            raise ValueError("length must be greater than zero")
        return hashlib.sha256(
            f"{self.master_seed}|{namespace}".encode("utf-8")
        ).hexdigest()[:length].upper()
