#!/usr/bin/env python3
"""Deterministic MadGraph builders for structured HEPToolBench tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PARTICLE_ALIASES = {
    "electron": "e-",
    "positron": "e+",
    "eminus": "e-",
    "eplus": "e+",
    "e-": "e-",
    "e+": "e+",
    "muon": "mu-",
    "antimuon": "mu+",
    "mu-": "mu-",
    "mu+": "mu+",
    "proton": "p",
    "p": "p",
    "top": "t",
    "anti-top": "t~",
    "anti top": "t~",
    "antitop": "t~",
    "tbar": "t~",
    "t": "t",
    "t~": "t~",
    "higgs": "h",
    "h": "h",
    "jet": "j",
    "jets": "j",
    "j": "j",
}

MODEL_ALIASES = {
    "standard model": "sm",
    "sm": "sm",
}


@dataclass
class ProcessParams:
    model: str = "sm"
    initial_state: list[str] = field(default_factory=lambda: ["p", "p"])
    final_state: list[str] = field(default_factory=lambda: ["e+", "e-"])
    beam_energy_gev: float = 6500.0
    output_dir: str = "DY_ee"
    nevents: int = 10000
    process_string: str | None = None


@dataclass
class RunCardParams:
    nevents: int = 10000
    iseed: int = 42
    ebeam1_gev: float = 6500.0
    ebeam2_gev: float = 6500.0
    ptl_min_gev: float = 20.0
    eta_l_max: float = 2.5


@dataclass
class WorkflowParams:
    model: str = "sm"
    initial_state: list[str] = field(default_factory=lambda: ["p", "p"])
    final_state: list[str] = field(default_factory=lambda: ["t", "t~"])
    beam_energy_gev: float = 6500.0
    output_dir: str = "TTbar_P8_Delphes"
    nevents: int = 10000
    iseed: int = 42
    shower: str = "Pythia8"
    detector: str = "Delphes"
    madspin: str = "OFF"
    process_string: str | None = None


def normalize_particle(name: Any) -> str:
    text = str(name).strip()
    key = text.lower().replace(" ", "")
    return PARTICLE_ALIASES.get(key, text)


def normalize_model(name: Any) -> str:
    text = str(name).strip()
    key = text.lower()
    return MODEL_ALIASES.get(key, text)


def params_from_dict(data: dict[str, Any]) -> ProcessParams:
    return ProcessParams(
        model=normalize_model(data.get("model", "sm")),
        initial_state=[normalize_particle(x) for x in data.get("initial_state", ["p", "p"])],
        final_state=[normalize_particle(x) for x in data.get("final_state", ["e+", "e-"])],
        beam_energy_gev=float(data.get("beam_energy_gev", 6500)),
        output_dir=str(data.get("output_dir", "DY_ee")).strip() or "DY_ee",
        nevents=int(data.get("nevents", 10000)),
        process_string=data.get("process_string"),
    )


def runcard_params_from_dict(data: dict[str, Any]) -> RunCardParams:
    return RunCardParams(
        nevents=int(data.get("nevents", 10000)),
        iseed=int(data.get("iseed", data.get("seed", 42))),
        ebeam1_gev=float(data.get("ebeam1_gev", data.get("ebeam1", 6500))),
        ebeam2_gev=float(data.get("ebeam2_gev", data.get("ebeam2", 6500))),
        ptl_min_gev=float(data.get("ptl_min_gev", data.get("ptl", 20))),
        eta_l_max=float(data.get("eta_l_max", data.get("etal", 2.5))),
    )


def workflow_params_from_dict(data: dict[str, Any]) -> WorkflowParams:
    madspin = str(data.get("madspin", "OFF")).strip()
    if madspin.lower() in {"off", "false", "disabled", "disable", "none", "no"}:
        madspin = "OFF"
    return WorkflowParams(
        model=normalize_model(data.get("model", "sm")),
        initial_state=[normalize_particle(x) for x in data.get("initial_state", ["p", "p"])],
        final_state=[normalize_particle(x) for x in data.get("final_state", ["t", "t~"])],
        beam_energy_gev=float(data.get("beam_energy_gev", 6500)),
        output_dir=str(data.get("output_dir", "TTbar_P8_Delphes")).strip() or "TTbar_P8_Delphes",
        nevents=int(data.get("nevents", 10000)),
        iseed=int(data.get("iseed", data.get("seed", 42))),
        shower=str(data.get("shower", "Pythia8")).strip() or "Pythia8",
        detector=str(data.get("detector", "Delphes")).strip() or "Delphes",
        madspin=madspin,
        process_string=data.get("process_string"),
    )


def clean_process_string(process: str) -> str:
    process = process.strip()
    if process.lower().startswith("generate "):
        process = process.split(None, 1)[1].strip()
    return process


def build_process_line(params: ProcessParams) -> str:
    if params.process_string and params.process_string.strip():
        process = clean_process_string(params.process_string)
    else:
        process = f"{' '.join(params.initial_state)} > {' '.join(params.final_state)}"
    return f"generate {process}"


def build_proc_card(params: ProcessParams) -> str:
    multiparticle_lines = ["define p = g u c d s u~ c~ d~ s~"]
    particles = params.initial_state + params.final_state
    if "j" in particles or (params.process_string and reuses_jet(params.process_string)):
        multiparticle_lines.append("define j = g u c d s u~ c~ d~ s~")

    return "\n".join(
        [
            f"import model {params.model}",
            *multiparticle_lines,
            build_process_line(params),
            f"output {params.output_dir}",
            "launch",
            f"set ebeam1 {params.beam_energy_gev:g}",
            f"set ebeam2 {params.beam_energy_gev:g}",
            "",
        ]
    )


def reuses_jet(process: str) -> bool:
    return any(token == "j" for token in process.replace(">", " ").split())


def build_run_card(params: RunCardParams) -> str:
    return "\n".join(
        [
            f"{params.nevents:g} = nevents",
            f"{params.iseed:g} = iseed",
            f"{params.ebeam1_gev:g} = ebeam1",
            f"{params.ebeam2_gev:g} = ebeam2",
            f"{params.ptl_min_gev:g} = ptl",
            f"{params.eta_l_max:g} = etal",
            "",
        ]
    )


def build_workflow_script(params: WorkflowParams) -> str:
    process_params = ProcessParams(
        model=params.model,
        initial_state=params.initial_state,
        final_state=params.final_state,
        beam_energy_gev=params.beam_energy_gev,
        output_dir=params.output_dir,
        nevents=params.nevents,
        process_string=params.process_string,
    )
    base_lines = build_proc_card(process_params).strip().splitlines()
    launch_index = base_lines.index("launch")
    return "\n".join(
        [
            *base_lines[: launch_index + 1],
            f"shower={params.shower}",
            f"detector={params.detector}",
            "analysis=OFF",
            f"madspin={params.madspin}",
            "done",
            f"set nevents {params.nevents:g}",
            f"set iseed {params.iseed:g}",
            f"set ebeam1 {params.beam_energy_gev:g}",
            f"set ebeam2 {params.beam_energy_gev:g}",
            "done",
            "",
        ]
    )
