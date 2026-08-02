#!/usr/bin/env python3
"""Score Task019 plot-ready scan-data JSON."""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from typing import Any

TASK_ID = "plot_data_019"
WEIGHTS = {
    "recoverable_output": 0.05,
    "status_plot_ready": 0.08,
    "scan_parameter_correct": 0.05,
    "labels_correct": 0.08,
    "x_values_correct": 0.18,
    "y_values_correct": 0.18,
    "yerr_values_correct": 0.10,
    "point_count_correct": 0.05,
    "log_y_correct": 0.10,
    "benchmark_marker_correct": 0.10,
    "safe_to_plot_correct": 0.03,
}
PASS_THRESHOLD = 0.85
EXPECTED_X = [1.0, 1.5, 2.0, 2.5, 3.0]
EXPECTED_Y = [12.40, 8.10, 5.00, 3.20, 1.70]
EXPECTED_ERR = [0.40, 0.30, 0.20, 0.10, 0.08]
REQUIRED = {"status","scan_parameter","x_values_gev","y_values_pb","yerr_values_pb","benchmark_marker"}

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")

def clean_text(text: str) -> str:
    text = OSC_RE.sub("", text)
    text = ANSI_RE.sub("", text)
    while "\b" in text:
        text = re.sub(r".?\x08", "", text, count=1)
    text = text.replace("\r", "\n")
    text = text.replace("```json", "```").replace("```JSON", "```").replace("```", "")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return text.strip()

def norm_text(x: Any) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(x).lower()).strip()

def object_quality(obj: Any, required: set[str]) -> int:
    if not isinstance(obj, dict):
        return -100
    score = sum(1 for k in required if k in obj)
    if len(obj) < 4:
        score -= 20
    return score

def parse_json_best(text: str, required: set[str]) -> tuple[Any | None, str]:
    original = text.strip()
    strict_candidate = (
        original.startswith("{")
        and original.endswith("}")
        and "```" not in original
        and not ANSI_RE.search(original)
        and not OSC_RE.search(original)
    )
    cleaned = clean_text(text)
    dec = json.JSONDecoder()
    candidates: list[Any] = []
    try:
        obj = json.loads(cleaned)
        return obj, "strict" if strict_candidate else "recovered_json_substring"
    except Exception:
        pass
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(cleaned[i:])
            if isinstance(obj, dict):
                candidates.append(obj)
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda o: object_quality(o, required), reverse=True)
        return candidates[0], "recovered_json_substring"
    repaired = re.sub(r",\s*([}\]])", r"\1", cleaned)
    for i, ch in enumerate(repaired):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(repaired[i:])
            if isinstance(obj, dict):
                candidates.append(obj)
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda o: object_quality(o, required), reverse=True)
        return candidates[0], "recovered_after_trailing_comma_repair"
    return None, "not_parseable_json"

def get_number(obj: dict[str, Any], keys: list[str], raw: str = "") -> float | None:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            v = obj[k]
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                return float(v)
            m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(v))
            if m:
                return float(m.group(0))
    if raw:
        for k in keys:
            pat = re.compile(r'"?'+re.escape(k)+r'"?\s*:\s*"?\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', re.I)
            m = pat.search(raw)
            if m:
                return float(m.group(1))
    return None

def get_bool(obj: dict[str, Any], keys: list[str], raw: str = "") -> bool | None:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            v = obj[k]
            if isinstance(v, bool):
                return v
            s = norm_text(v)
            if s in {"true", "yes", "safe", "complete", "completed"}:
                return True
            if s in {"false", "no", "unsafe", "incomplete"}:
                return False
    if raw:
        for k in keys:
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*(true|false|yes|no)', raw, re.I)
            if m:
                return m.group(1).lower() in {"true","yes"}
    return None

def get_string(obj: dict[str, Any], keys: list[str], raw: str = "") -> str:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            return str(obj[k])
    if raw:
        for k in keys:
            # stop at next quoted key if possible
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*"([^"]*)"', raw, re.I|re.S)
            if m:
                return m.group(1)
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*([^,\n}]+)', raw, re.I|re.S)
            if m:
                return m.group(1)
    return ""

def extract_list_from_obj_or_raw(obj: dict[str, Any], keys: list[str], raw: str = "") -> list[float]:
    val = None
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            val = obj[k]
            break
    if val is None and raw:
        for k in keys:
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*\[([^\]]*)\]', raw, re.I|re.S)
            if m:
                val = m.group(1)
                break
    vals: list[float] = []
    if isinstance(val, list):
        items = val
    else:
        items = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(val or ""))
    for item in items:
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            x = float(item)
        else:
            m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(item))
            if not m:
                continue
            x = float(m.group(0))
        if not any(math.isclose(x, y, abs_tol=1e-6) for y in vals):
            vals.append(x)
    return vals

def lists_close(got: list[float], exp: list[float], tol: float = 1e-6) -> bool:
    return len(got) == len(exp) and all(math.isclose(a, b, abs_tol=tol, rel_tol=0) for a, b in zip(got, exp))

def lists_match_set(got: list[float], exp: list[float], tol: float = 1e-6) -> bool:
    return len(got) == len(exp) and all(any(math.isclose(x, y, abs_tol=tol, rel_tol=0) for x in got) for y in exp)


def nested_number(obj: dict[str, Any], parent: str, keys: list[str], raw: str="") -> float | None:
    if isinstance(obj, dict) and isinstance(obj.get(parent), dict):
        v = get_number(obj[parent], keys, "")
        if v is not None:
            return v
    if raw:
        m = re.search(r'"?'+re.escape(parent)+r'"?\s*:\s*\{([^}]*)\}', raw, re.I|re.S)
        if m:
            return get_number({}, keys, m.group(1))
    return None

def score_submission(path: Path) -> dict[str, Any]:
    raw0 = path.read_text(errors="replace")
    raw = clean_text(raw0)
    obj, parse_mode = parse_json_best(raw0, REQUIRED)
    strict_json = parse_mode == "strict"
    if obj is None:
        obj = {}
    checks = {k: False for k in WEIGHTS}
    failure_modes = []
    norm = {}

    checks["recoverable_output"] = bool(obj) or ("x_values" in raw and "y_values" in raw)
    if not checks["recoverable_output"]:
        failure_modes.append(parse_mode)
    elif parse_mode != "strict":
        failure_modes.append(parse_mode)

    status = norm_text(get_string(obj, ["status"], raw))
    checks["status_plot_ready"] = ("plot" in status and "ready" in status and "not" not in status) or status == "ready"
    if not checks["status_plot_ready"]:
        failure_modes.append("status_not_plot_ready")
    norm["status"] = get_string(obj, ["status"], raw)

    sp = get_string(obj, ["scan_parameter","parameter"], raw).lower()
    sp_norm = re.sub(r"\bgev\b|\[|\]|\(|\)|/|unit|mass", "", sp)
    sp_norm = re.sub(r"[^a-z0-9]+", "", sp_norm)
    checks["scan_parameter_correct"] = sp_norm == "ms"
    if not checks["scan_parameter_correct"]:
        failure_modes.append("scan_parameter_wrong")
    norm["scan_parameter"] = sp

    xl = norm_text(get_string(obj, ["x_label"], raw))
    yl = norm_text(get_string(obj, ["y_label"], raw))
    checks["labels_correct"] = ("ms" in xl and "gev" in xl and ("cross" in yl or "sigma" in yl) and "pb" in yl)
    if not checks["labels_correct"]:
        failure_modes.append("labels_wrong")
    norm["x_label"] = xl; norm["y_label"] = yl

    xs = extract_list_from_obj_or_raw(obj, ["x_values_gev","x_values","masses_gev"], raw)
    ys = extract_list_from_obj_or_raw(obj, ["y_values_pb","cross_sections_pb","sigma_pb"], raw)
    es = extract_list_from_obj_or_raw(obj, ["yerr_values_pb","y_errors_pb","uncertainties_pb","stat_uncertainty_pb"], raw)
    checks["x_values_correct"] = lists_close(xs, EXPECTED_X, 1e-6)
    checks["y_values_correct"] = lists_close(ys, EXPECTED_Y, 1e-6)
    checks["yerr_values_correct"] = lists_close(es, EXPECTED_ERR, 1e-6)
    if not checks["x_values_correct"]: failure_modes.append("x_values_wrong")
    if not checks["y_values_correct"]: failure_modes.append("y_values_wrong")
    if not checks["yerr_values_correct"]: failure_modes.append("yerr_values_wrong")
    norm["x_values_gev"] = xs; norm["y_values_pb"] = ys; norm["yerr_values_pb"] = es

    n = get_number(obj, ["number_of_plot_points","plot_points","n_points"], raw)
    checks["point_count_correct"] = n is not None and int(round(n)) == 5
    if not checks["point_count_correct"]:
        failure_modes.append("point_count_wrong")
    norm["number_of_plot_points"] = n

    logy = get_bool(obj, ["log_y","log_scale_y","use_log_y"], raw)
    checks["log_y_correct"] = logy is True
    if not checks["log_y_correct"]:
        failure_modes.append("log_y_wrong")
    norm["log_y"] = logy

    bm = nested_number(obj, "benchmark_marker", ["mass_gev","benchmark_mass_gev","mass"], raw)
    bs = nested_number(obj, "benchmark_marker", ["cross_section_pb","sigma_pb","benchmark_cross_section_pb"], raw)
    if bm is None:
        bm = get_number(obj, ["benchmark_mass_gev","selected_mass_gev"], raw)
    if bs is None:
        bs = get_number(obj, ["benchmark_cross_section_pb","selected_cross_section_pb"], raw)
    checks["benchmark_marker_correct"] = bm is not None and bs is not None and math.isclose(bm,1.5,abs_tol=1e-6) and math.isclose(bs,8.10,abs_tol=1e-3)
    if not checks["benchmark_marker_correct"]:
        failure_modes.append("benchmark_marker_wrong")
    norm["benchmark_marker"] = {"mass_gev": bm, "cross_section_pb": bs}

    safe = get_bool(obj, ["safe_to_plot","safe_to_make_final_plot"], raw)
    checks["safe_to_plot_correct"] = safe is True
    if not checks["safe_to_plot_correct"]:
        failure_modes.append("safe_to_plot_wrong")
    norm["safe_to_plot"] = safe

    score = round(sum(WEIGHTS[k] for k, ok in checks.items() if ok), 6)
    passed = score >= PASS_THRESHOLD
    return {"task_id": TASK_ID, "submission": str(path), "score": score, "passed": passed,
            "strict_passed": strict_json and passed, "checks": checks,
            "failure_modes": failure_modes, "normalized_plot_data": norm}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--submission", required=True, type=Path)
    p.add_argument("--output", type=Path)
    a=p.parse_args()
    res=score_submission(a.submission)
    txt=json.dumps(res,indent=2,sort_keys=True)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(txt+"\n")
    print(txt)
if __name__=="__main__":
    main()
