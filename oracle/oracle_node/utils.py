import os
import re

def sanitize_bag_path(uri: str) -> str:
    if not isinstance(uri, str):
        return ""
    if uri.startswith("file://"):
        return uri[len("file://"):]
    return uri

def reason_from_output(out_text: str) -> str:
    lines = out_text.splitlines()
    fail_base = next((ln for ln in lines if "Base path:" in ln and "FAIL" in ln), None)
    fail_stop = next((ln for ln in lines if "Stops pattern:" in ln and "FAIL" in ln), None)
    fail_arm  = next((ln for ln in lines if re.search(r"^\s*Arm:\s*FAIL", ln)), None)
    fail_disp = next((ln for ln in lines if "Disposal event:" in ln and "FAIL" in ln), None)

    if fail_base:
        m = re.search(r"total\s+([0-9.]+)\s*m,\s*min\s*([0-9.]+)", fail_base)
        if m:
            return f"Base path too short, total {m.group(1)} m, min {m.group(2)} m"
        return "Base path too short"
    if fail_stop:
        m = re.search(r"observed\s+(\d+)\s+segments", fail_stop)
        if m:
            return f"Stop move stop pattern missing, observed {m.group(1)} segments"
        return "Stop move stop pattern missing"
    if fail_arm:
        m = re.search(r"net delta\s*([0-9.]+)\s*rad,\s*tol\s*([0-9.]+).*moves\s*(\d+)", fail_arm)
        if m:
            return f"Arm motion below threshold, net {m.group(1)} rad, tol {m.group(2)} rad, moves {m.group(3)}"
        return "Arm motion below threshold"
    if fail_disp:
        return "Disposal event with correct flag not seen"

    snippet = out_text.strip().splitlines()[-1] if out_text.strip() else "No details"
    return f"Validator rejected, {snippet[:80]}"
