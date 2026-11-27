"""
Energy validator for legacy CSV proofs (e.g. a charging power log), as in the
original oracle: the CSV must parse into an energy figure, which is reported.
Like the ROS 1 bag, a CSV carries no manifest and is not bound to a task.
"""
from __future__ import annotations

from ..power_csv import compute_energy_and_coins
from . import Verdict


def validate_csv(path: str, iec_per_kwh: float, iec_decimals: int) -> Verdict:
    v = Verdict(ok=True)
    v.lines.append("  INFO  legacy CSV proof: not bound to a task (no manifest)")
    try:
        res = compute_energy_and_coins(path, iec_per_kwh, iec_decimals)
    except Exception as e:  # noqa: BLE001
        v.check(False, f"CSV parse failed: {e}", f"CSV parse failed, {e}")
        return v
    v.check(res.rows > 0, f"rows {res.rows}", "CSV has no rows")
    v.lines.append(f"  INFO  energy {res.energy_Wh:.6f} Wh ({res.energy_kWh:.9f} kWh), "
                   f"{res.coins_IEC_float:.9f} IEC at {iec_per_kwh} IEC/kWh")
    return v
