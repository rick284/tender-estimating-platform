"""Build tests/golden_weather_rev2.json: scenarios run through the REAL NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx,
recalculated by LibreOffice, so tender_engine.weather_tool can be tested against the workbook's own answers.

Run:  python tools/make_weather_golden.py private/NZ_Weather_Tool_Rev2.xlsx [n_scenarios]
Needs LibreOffice (soffice). The fixture contains only synthetic inputs and the tool's numbers (no client data).
"""
from __future__ import annotations
import datetime as dt
import json
import random
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tender_engine.weather_tool import stations, task_names  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "golden_weather_rev2.json"
OVR = {"rain_exposure": "I", "rain_loss": "L", "carryover": "O", "wind_sensitivity": "R", "wind_loss": "U", "nonrecoverable": "X"}
OUTCOLS = {"workdays": "Z", "wet_probability": "AA", "adjusted_wet_probability": "AB", "wind_probability": "AC", "rain_impact": "AD",
           "carryover_impact": "AE", "wind_impact": "AF", "combined_impact": "AG", "direct_allowance": "AH", "lost_wd": "AI",
           "cp_delay_wd": "AJ", "status": "AK"}


def scenario(rng: random.Random, i: int) -> dict:
    st = ["Auckland", "Auckland", "Christchurch", "Queenstown", "Wellington", "Kaitaia", "Hokitika", "Chatham Islands"][i % 8] if i < 16 else rng.choice(stations())
    acts = []
    for _ in range(rng.randint(1, 6)):
        s = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randint(0, 5800 - 400))
        f = s + dt.timedelta(days=rng.choice([0, 1, 4, 11, 30, 75, 130, 380]))
        ov = {k: rng.choice([0.1, 0.5, 0.75, 1.0]) for k in rng.sample(list(OVR), rng.choice([0, 0, 1, 2]))}
        acts.append({"task": rng.choice(task_names()), "start": s.isoformat(), "finish": f.isoformat(), "critical": rng.random() < 0.5,
                     "labour": rng.choice([0, 1000, 12345.67, 50000]), "plant": rng.choice([0, 2500, 33333.33]), "overrides": ov})
    return {"station": st, "working_days_per_week": rng.choice([5, 5, 5, 6, 7, 4]), "local_factor": rng.choice([1, 1, 1.15, 0.8]),
            "wind_override": rng.choice([None, None, None, 0.1]), "daily_prelims": rng.choice([0, 584, 666.5]),
            "weekly_hire": rng.choice([0, 295, 1234.5]), "recovery": rng.choice([0, 0, 1500]), "activities": acts}


def build(src: str, sc: dict, path: Path) -> None:
    wb = openpyxl.load_workbook(src)
    wb["Estimator"]["B4"] = sc["station"]
    wb["Estimator"]["B7"] = sc["working_days_per_week"]
    aa = wb["Activity Allowances"]
    aa["B3"] = sc["local_factor"]; aa["D3"] = sc["wind_override"]; aa["F3"] = sc["daily_prelims"]; aa["H3"] = sc["weekly_hire"]; aa["J3"] = sc["recovery"]
    for i, a in enumerate(sc["activities"]):
        r = 7 + i
        aa[f"A{r}"] = a["task"]; aa[f"C{r}"] = dt.datetime.fromisoformat(a["start"]); aa[f"D{r}"] = dt.datetime.fromisoformat(a["finish"])
        aa[f"E{r}"] = "Yes" if a["critical"] else "No"; aa[f"F{r}"] = a["labour"]; aa[f"G{r}"] = a["plant"]
        for k, v in a["overrides"].items():
            aa[f"{OVR[k]}{r}"] = v
    wb.save(path)


def main(src: str, n: int) -> None:
    rng = random.Random(20261012)
    scs = [scenario(rng, i) for i in range(n)]
    tmp = Path(tempfile.mkdtemp(prefix="wxgold_"))
    for i, sc in enumerate(scs):
        build(src, sc, tmp / f"s{i}.xlsx")
    outdir = tmp / "out"
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(outdir), *[str(tmp / f"s{i}.xlsx") for i in range(n)]],
                   check=True, capture_output=True, timeout=3000)
    for i, sc in enumerate(scs):
        v = openpyxl.load_workbook(outdir / f"s{i}.xlsx", data_only=True)["Activity Allowances"]
        sc["expected"] = {"activities": [{k: v[f"{c}{7 + j}"].value for k, c in OUTCOLS.items()} for j in range(len(sc["activities"]))],
                          "exposed_pool": v["B39"].value, "direct": v["B40"].value, "cp_delay_wd": v["B41"].value, "prelims": v["B42"].value,
                          "weeks": v["B43"].value, "hire": v["B44"].value, "recovery": v["B45"].value, "total": v["B46"].value}
    OUT.write_text(json.dumps({"source": "NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx recalculated in LibreOffice", "scenarios": scs}, indent=1, default=str) + "\n")
    shutil.rmtree(tmp)
    print("wrote", OUT, len(scs), "scenarios")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 24)
