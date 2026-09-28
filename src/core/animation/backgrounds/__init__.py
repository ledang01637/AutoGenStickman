from .street_food import build_background_street_food
from .park_day    import build_background_park_day
from .office      import build_background_office
from .gym         import build_background_gym
from .city_day    import build_background_city_day
from .cafe        import build_background_cafe
from .bedroom     import build_background_bedroom

# animate functions tập trung 1 file, tránh phải sửa 7 file riêng
from .animate_backgrounds import (
    animate_background_office,
    animate_background_park_day,
    animate_background_gym,
    animate_background_cafe,
    animate_background_bedroom,
    animate_background_city_day,
    animate_background_street_food,
)

BACKGROUND_FN = {
    "office":      build_background_office,
    "bedroom":     build_background_bedroom,
    "city_day":    build_background_city_day,
    "park_day":    build_background_park_day,
    "cafe":        build_background_cafe,
    "gym":         build_background_gym,
    "street_food": build_background_street_food,
}

BACKGROUND_ANIMATE_FN = {
    "office":      animate_background_office,
    "bedroom":     animate_background_bedroom,
    "city_day":    animate_background_city_day,
    "park_day":    animate_background_park_day,
    "cafe":        animate_background_cafe,
    "gym":         animate_background_gym,
    "street_food": animate_background_street_food,
}

__all__ = ["BACKGROUND_FN", "BACKGROUND_ANIMATE_FN"]