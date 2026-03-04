# power_csv.py
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Tuple, Optional
import csv, re, math

TS_RE = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2}))'
)
NUM_RE = re.compile(r'-?\d+(?:\.\d+)?')

@dataclass
class EnergyResult:
    rows: int
    energy_Wh: float
    energy_kWh: float
    coins_IEC: int
    coins_IEC_float: float

def _parse_iso(ts: str) -> datetime:
    ts = ts.strip().rstrip(",")
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)

def _float_or_none(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    m = NUM_RE.search(s)
    return float(m.group(0)) if m else None

def _parse_structured(reader: csv.DictReader) -> List[Tuple[datetime, float]]:
    points: List[Tuple[datetime, float]] = []
    has_ts = any(k.lower().startswith("timestamp") for k in reader.fieldnames or [])
    for row in reader:
        try:
            ts_raw = row.get("timestamp_iso") or row.get("timestamp") or row.get(next(iter(row)))
            if not has_ts or not ts_raw:
                raise ValueError("no timestamp column")
            ts = _parse_iso(str(ts_raw))
            p = _float_or_none(row.get("power"))
            if p is None:
                i = _float_or_none(row.get("current"))
                v = _float_or_none(row.get("voltage"))
                if i is not None and v is not None:
                    p = i * v
            if p is None:
                # last try, any column that looks like power
                for k, v in row.items():
                    if k and "power" in k.lower():
                        p = _float_or_none(v)
                        break
            if p is None:
                continue
            points.append((ts, float(p)))
        except Exception:
            continue
    return points

def _parse_unstructured_line(line: str) -> Optional[Tuple[datetime, float]]:
    m_ts = TS_RE.search(line)
    if not m_ts:
        return None
    ts = _parse_iso(m_ts.group("ts"))
    # Prefer explicit power
    m_pow = re.search(r'power\s*[:=]\s*([-+]?\d+(?:\.\d+)?)', line, re.I)
    if m_pow:
        p = float(m_pow.group(1))
        return ts, p
    # Else try current and voltage
    m_i = re.search(r'current\s*[:=]\s*([-+]?\d+(?:\.\d+)?)', line, re.I)
    m_v = re.search(r'voltage\s*[:=]\s*([-+]?\d+(?:\.\d+)?)', line, re.I)
    if m_i and m_v:
        return ts, float(m_i.group(1)) * float(m_v.group(1))
    # Else any trailing comma separated number as power
    tail_nums = NUM_RE.findall(line.split(",")[-1])
    if tail_nums:
        return ts, float(tail_nums[-1])
    return None

def _parse_rows(path: str) -> List[Tuple[datetime, float]]:
    # First attempt, structured CSV
    with open(path, "r", newline="") as f:
        try:
            f.seek(0)
            reader = csv.DictReader(f)
            pts = _parse_structured(reader)
            if pts:
                pts.sort(key=lambda x: x[0])
                return pts
        except Exception:
            pass

    # Fallback, unstructured log style lines
    points: List[Tuple[datetime, float]] = []
    with open(path, "r", newline="") as f:
        for line in f:
            line = line.strip()
            if not line or line.lower().startswith("timestamp"):
                continue
            parsed = _parse_unstructured_line(line)
            if parsed:
                points.append(parsed)
    points.sort(key=lambda x: x[0])
    return points

def _integrate_Wh(points: List[Tuple[datetime, float]]) -> float:
    if len(points) < 2:
        return 0.0
    wh = 0.0
    for (t0, p0), (t1, p1) in zip(points, points[1:]):
        dt_s = (t1 - t0).total_seconds()
        if dt_s <= 0:
            continue
        wh += 0.5 * (p0 + p1) * dt_s / 3600.0
    return wh

def compute_energy_and_coins(csv_path: str, iec_per_kwh: float, token_decimals: int = 18) -> EnergyResult:
    pts = _parse_rows(csv_path)
    if not pts:
        raise ValueError("no usable rows found")
    wh = _integrate_Wh(pts)
    kwh = wh / 1000.0
    coins_float = kwh * iec_per_kwh
    coins_wei = int(round(coins_float * (10 ** token_decimals)))
    return EnergyResult(
        rows=len(pts),
        energy_Wh=wh,
        energy_kWh=kwh,
        coins_IEC=coins_wei,
        coins_IEC_float=coins_float,
    )
