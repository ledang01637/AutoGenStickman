# motion.py
def ease_in_out_cubic(t: float) -> float:
    """
    Cubic ease-in-out: t ∈ [0, 1] → progress ∈ [0, 1]
    Tăng tốc đầu, giảm tốc cuối — tự nhiên hơn linear.
    """
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - (-2 * t + 2) ** 3 / 2


def get_character_x(x_start: float, x_end: float,
                    t_start: float, t_end: float,
                    t: float) -> float:
    """
    Tọa độ x của nhân vật tại thời điểm t.
    Dùng cubic ease-in-out để tăng/giảm tốc tự nhiên.
    """
    if t <= t_start:
        return x_start
    if t >= t_end:
        return x_end

    # Normalize t về [0, 1]
    progress = (t - t_start) / (t_end - t_start)

    # Ease
    eased = ease_in_out_cubic(progress)

    # LERP
    return x_start + (x_end - x_start) * eased