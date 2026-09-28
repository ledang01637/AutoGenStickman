from ..constants import PoseFn

from .locomotion  import pose_walk, pose_run
from .standing    import pose_idle, pose_talk, pose_shrug
from .interaction import pose_drink, pose_eat, pose_hold

POSE_FN: dict[str, PoseFn] = {
    "walk"  : pose_walk,
    "run"   : pose_run,
    "idle"  : pose_idle,
    "talk"  : pose_talk,
    "shrug" : pose_shrug,
    "drink" : pose_drink,
    "eat"   : pose_eat,
    "hold"  : pose_hold,
}