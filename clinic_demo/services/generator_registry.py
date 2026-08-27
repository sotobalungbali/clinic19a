"""Explicit generator registry. Domain generators are added in later prompts."""

from collections import defaultdict, deque


class GeneratorRegistry:
    def __init__(self):
        self._by_key = {}

    def register(self, generator_class):
        key = generator_class.key
        if not key:
            raise ValueError("Generator key is required.")
        if key in self._by_key:
            raise ValueError(f"Duplicate generator key: {key}")
        self._by_key[key] = generator_class
        return generator_class

    def get(self, key):
        return self._by_key[key]

    def all(self):
        return tuple(self._by_key[key] for key in sorted(self._by_key))

    def validate(self):
        keys = set(self._by_key)
        unknown = []
        for generator in self._by_key.values():
            for dependency in generator.depends_on:
                if dependency not in keys:
                    unknown.append((generator.key, dependency))
        if unknown:
            raise ValueError(f"Unknown generator dependencies: {unknown}")

        indegree = {key: 0 for key in keys}
        children = defaultdict(set)
        for generator in self._by_key.values():
            for dependency in generator.depends_on:
                indegree[generator.key] += 1
                children[dependency].add(generator.key)

        ready = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        seen = []
        while ready:
            key = ready.popleft()
            seen.append(key)
            for child in sorted(children[key]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(seen) != len(keys):
            raise ValueError("Generator dependency graph contains a cycle.")
        return True


GENERATOR_REGISTRY = GeneratorRegistry()
