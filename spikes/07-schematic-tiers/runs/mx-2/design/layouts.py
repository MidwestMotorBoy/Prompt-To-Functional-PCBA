"""Layout programs for blocks. A block asks for one with kernel.layout(kind, **params); draw.py runs it on a Scene
(see sch.py) instead of the automatic placer. Each program is a short script: place parts, connect pins."""
import sch
from sch import Port, snap

REGISTRY = {}


def layout(kind):
    def deco(fn):
        REGISTRY[kind] = fn
        return fn
    return deco
