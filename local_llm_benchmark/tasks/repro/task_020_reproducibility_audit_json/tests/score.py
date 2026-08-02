#!/usr/bin/env python3
"""Score Task020 reproducibility audit JSON."""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from typing import Any

TASK_ID = "repro_audit_020"
WEIGHTS = {
    "recoverable_output": 0.05,
    "status_not_reproducible": 0.15,
    "detector_level_claimed_false": 0.10,
    "missing_required_files_correct": 0.25,
    "missing_optional_files_correct": 0.10,
    "affected_scan_points_correct": 0.10,
    "can_reproduce_false": 0.10,
    "safe_archive_false": 0.10,
    "recommended_action_correct": 0.05,
}
PASS_THRESHOLD = 0.85
REQ_FILES = ["cards/param_cards/mS_2p5.dat", "logs/mS_2p5_seed.txt"]
OPT_FILES = ["cards/pythia8.cmnd", "cards/delphes_card.dat"]
REQUIRED = {"status","detector_level_claimed","missing_required_files","affected_scan_points_gev","safe_for_paper_archive"}

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


def norm_path(s: str) -> str:
    s = str(s).strip().strip('"').strip("'")
    s = s.replace("\\", "/")
    s = re.sub(r"\s+", "", s)
    return s.lower()

def extract_string_list(obj: dict[str, Any], keys: list[str], raw: str = "") -> list[str]:
    val = None
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            val = obj[k]; break
    if val is None and raw:
        for k in keys:
            m = re.search(r'"?'+re.escape(k)+r'"?\s*:\s*\[([^\]]*)\]', raw, re.I|re.S)
            if m:
                val = m.group(1); break
    if isinstance(val, list):
        items = val
    else:
        items = re.findall(r'"([^"]+)"|([A-Za-z0-9_./-]+\.(?:dat|txt|cmnd))', str(val or ""))
        items = [a or b for a,b in items]
    out = []
    for item in items:
        st = str(item)
        if st and st not in out:
            out.append(st)
    return out

def paths_match(got: list[str], exp: list[str]) -> bool:
    ng = [norm_path(x) for x in got]
    ne = [norm_path(x) for x in exp]
    return len(ng) == len(ne) and all(any(x == y for x in ng) for y in ne)

def score_submission(path: Path) -> dict[str, Any]:
    raw0 = path.read_text(errors="replace")
    raw = clean_text(raw0)
    obj, parse_mode = parse_json_best(raw0, REQUIRED)
    strict_json = parse_mode == "strict"
    if obj is None: obj = {}
    checks = {k: False for k in WEIGHTS}
    failures = []
    norm = {}

    checks["recoverable_output"] = bool(obj) or ("missing_required" in raw or "mS_2p5" in raw)
    if not checks["recoverable_output"]:
        failures.append(parse_mode)
    elif parse_mode != "strict":
        failures.append(parse_mode)

    status = norm_text(get_string(obj, ["status"], raw))
    checks["status_not_reproducible"] = ("not" in status and "repro" in status) or "incomplete" in status or "missing" in status
    if not checks["status_not_reproducible"]:
        failures.append("status_wrong")
    norm["status"] = get_string(obj, ["status"], raw)

    det = get_bool(obj, ["detector_level_claimed","detector_level_results_claimed"], raw)
    checks["detector_level_claimed_false"] = det is False
    if not checks["detector_level_claimed_false"]:
        failures.append("detector_level_claim_wrong")
    norm["detector_level_claimed"] = det

    req = extract_string_list(obj, ["missing_required_files","required_missing_files"], raw)
    opt = extract_string_list(obj, ["missing_optional_files","optional_missing_files"], raw)
    checks["missing_required_files_correct"] = paths_match(req, REQ_FILES)
    if not checks["missing_required_files_correct"]:
        failures.append("missing_required_files_wrong")
    checks["missing_optional_files_correct"] = paths_match(opt, OPT_FILES)
    if not checks["missing_optional_files_correct"]:
        failures.append("missing_optional_files_wrong")
    norm["missing_required_files"] = req
    norm["missing_optional_files"] = opt

    pts = extract_list_from_obj_or_raw(obj, ["affected_scan_points_gev","affected_masses_gev","missing_scan_points_gev"], raw)
    checks["affected_scan_points_correct"] = lists_close(pts, [2.5], 1e-6)
    if not checks["affected_scan_points_correct"]:
        failures.append("affected_scan_points_wrong")
    norm["affected_scan_points_gev"] = pts

    repro = get_bool(obj, ["can_reproduce_parton_level_scan","reproducible","can_reproduce"], raw)
    checks["can_reproduce_false"] = repro is False
    if not checks["can_reproduce_false"]:
        failures.append("can_reproduce_wrong")
    norm["can_reproduce_parton_level_scan"] = repro

    safe = get_bool(obj, ["safe_for_paper_archive","safe_to_archive","paper_archive_safe"], raw)
    checks["safe_archive_false"] = safe is False
    if not checks["safe_archive_false"]:
        failures.append("safe_archive_wrong")
    norm["safe_for_paper_archive"] = safe

    action = norm_text(get_string(obj, ["recommended_action","next_action"], raw))
    checks["recommended_action_correct"] = ("2p5" in action or "2 5" in action or "2.5" in action) and ("param" in action) and ("seed" in action)
    if not checks["recommended_action_correct"]:
        failures.append("recommended_action_incomplete")
    norm["recommended_action"] = get_string(obj, ["recommended_action","next_action"], raw)

    score = round(sum(WEIGHTS[k] for k, ok in checks.items() if ok), 6)
    passed = score >= PASS_THRESHOLD
    return {"task_id": TASK_ID, "submission": str(path), "score": score, "passed": passed,
            "strict_passed": strict_json and passed, "checks": checks,
            "failure_modes": failures, "normalized_audit": norm}

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
