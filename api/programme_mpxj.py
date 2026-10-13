"""Read and write MS Project files through MPXJ (a Java library), driven from Python with JPype.

The JVM is heavy, so the API never starts it inside the web server: `parse_file` / `export_xml` are called by a short-lived
helper process (`run_worker`), which exits when done and hands its memory back. The helper is this same file run as
`python programme_mpxj.py parse IN OUT.json` or `python programme_mpxj.py export IN.json OUT.xml`.

Reads .mpp / .mpx / .mpt / .xml / .planner / .pmxml / .xer. Writes MS Project XML (MSPDI): open it in MS Project and
Save As .mpp there (MPXJ cannot write the binary .mpp format).
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

JVM_MAX_HEAP = os.environ.get("MPXJ_JVM_HEAP", "-Xmx256m")


def _lib_dir() -> str:
    import mpxj
    d = os.path.join(os.path.dirname(mpxj.__file__), "lib")
    if not os.path.isdir(d):
        raise FileNotFoundError("The MPXJ library files were not found (is the mpxj package installed?).")
    return d


def ensure_jvm_started() -> None:
    import jpype
    if jpype.isJVMStarted():
        return
    lib = _lib_dir()
    jars = [os.path.join(lib, f) for f in os.listdir(lib) if f.endswith(".jar")]
    try:
        jvm = jpype.getDefaultJVMPath()
    except Exception as e:  # no Java installed
        raise RuntimeError("Java is not installed on the server, so MS Project files cannot be read yet.") from e
    jpype.startJVM(jvm, JVM_MAX_HEAP, "-Djava.awt.headless=true", classpath=jars)


def _s(value) -> Optional[str]:
    """Java object -> ISO string / str, None-safe."""
    if value is None:
        return None
    return str(value)


def _f(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.doubleValue())
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def _duration(d) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    try:
        return {"value": float(d.getDuration()), "unit": str(d.getUnits()).upper()}
    except Exception:
        return None


def _bool(value) -> bool:
    try:
        return bool(value)
    except Exception:
        return False


REL_TYPES = {"FINISH_START": "FS", "START_START": "SS", "FINISH_FINISH": "FF", "START_FINISH": "SF"}


def parse_file(file_path: str) -> Dict[str, Any]:
    import jpype
    ensure_jvm_started()
    File = jpype.JClass("java.io.File")
    Reader = jpype.JClass("org.mpxj.reader.UniversalProjectReader")
    TimeUnit = jpype.JClass("org.mpxj.TimeUnit")

    project = Reader().read(File(file_path))
    if project is None:
        raise ValueError("Could not read this file as a project programme")

    props = project.getProjectProperties()

    # Project-level working time (used for non-working shading in the chart)
    working_days = [True] * 7  # Mon..Sun
    hours_per_day = 8.0
    try:
        cal = project.getDefaultCalendar()
        if cal is not None:
            DayOfWeek = jpype.JClass("java.time.DayOfWeek")
            for i, dow in enumerate(DayOfWeek.values()):
                working_days[i] = bool(cal.isWorkingDay(dow))
            hpd = cal.getMinutesPerDay()
            if hpd is not None:
                hours_per_day = float(hpd) / 60.0
    except Exception:
        pass

    # Non-working dates (holidays etc.) from the default calendar's exceptions
    non_working_dates: List[str] = []
    try:
        cal = project.getDefaultCalendar()
        if cal is not None:
            for ex in cal.getCalendarExceptions():
                if ex.getWorking():
                    continue
                d0, d1 = ex.getFromDate(), ex.getToDate()
                if d0 is None or d1 is None:
                    continue
                cur = d0
                guard = 0
                while not cur.isAfter(d1) and guard < 800:
                    non_working_dates.append(str(cur))
                    cur = cur.plusDays(1)
                    guard += 1
    except Exception:
        pass

    tasks: List[Dict[str, Any]] = []
    for task in project.getTasks():
        uid = task.getUniqueID()
        tid = task.getID()
        if tid is None or int(tid) == 0:  # project summary row
            continue

        preds = []
        try:
            for rel in task.getPredecessors():
                pt = rel.getPredecessorTask()
                if pt is None:
                    continue
                lag = rel.getLag()
                lag_days = 0.0
                if lag is not None:
                    try:
                        lag_days = float(lag.convertUnits(TimeUnit.DAYS, props).getDuration())
                    except Exception:
                        lag_days = 0.0
                preds.append({
                    "id": int(pt.getID()),
                    "uid": int(pt.getUniqueID()) if pt.getUniqueID() is not None else int(pt.getID()),
                    "type": REL_TYPES.get(str(rel.getType()), "FS"),
                    "lag_days": lag_days,
                })
        except Exception:
            pass

        resources = []
        try:
            for a in task.getResourceAssignments():
                r = a.getResource()
                if r is not None and r.getName() is not None:
                    resources.append(str(r.getName()))
        except Exception:
            pass

        parent = task.getParentTask()
        constraint = task.getConstraintType()

        tasks.append({
            "id": int(tid),
            "uid": int(uid) if uid is not None else int(tid),
            "name": str(task.getName() or ""),
            "wbs": str(task.getWBS() or ""),
            "outline_level": int(task.getOutlineLevel() or 1),
            "parent_id": int(parent.getID()) if parent is not None and parent.getID() is not None and int(parent.getID()) != 0 else None,
            "is_summary": _bool(task.getSummary()),
            "is_milestone": _bool(task.getMilestone()),
            "is_critical": _bool(task.getCritical()),
            "is_active": task.getActive() is None or _bool(task.getActive()),
            "start": _s(task.getStart()),
            "finish": _s(task.getFinish()),
            "duration": _duration(task.getDuration()),
            "percent_complete": _f(task.getPercentageComplete()) or 0.0,
            "actual_start": _s(task.getActualStart()),
            "actual_finish": _s(task.getActualFinish()),
            "baseline_start": _s(task.getBaselineStart()),
            "baseline_finish": _s(task.getBaselineFinish()),
            "deadline": _s(task.getDeadline()),
            "constraint_type": str(constraint) if constraint is not None else None,
            "constraint_date": _s(task.getConstraintDate()),
            "total_slack": _duration(task.getTotalSlack()),
            "predecessors": preds,
            "resources": resources,
            "notes": str(task.getNotes() or ""),
        })

    return {
        "name": str(props.getName() or "Programme"),
        "start": _s(props.getStartDate()),
        "finish": _s(props.getFinishDate()),
        "status_date": _s(props.getStatusDate()),
        "author": str(props.getAuthor() or ""),
        "company": str(props.getCompany() or ""),
        "working_days": working_days,  # index 0 = Monday
        "non_working_dates": sorted(set(non_working_dates)),
        "hours_per_day": hours_per_day,
        "task_count": len(tasks),
        "tasks": tasks,
    }


# ---------------------------------------------------------------- export

_REL_FROM = {"FS": "FINISH_START", "SS": "START_START", "FF": "FINISH_FINISH", "SF": "START_FINISH"}


def export_xml(doc: Dict[str, Any], out_path: str) -> str:
    """Write a stored programme as MS Project XML (MSPDI) that opens in MS Project."""
    import jpype
    ensure_jvm_started()
    ProjectFile = jpype.JClass("org.mpxj.ProjectFile")
    Writer = jpype.JClass("org.mpxj.mspdi.MSPDIWriter")
    Duration = jpype.JClass("org.mpxj.Duration")
    TimeUnit = jpype.JClass("org.mpxj.TimeUnit")
    RelationType = jpype.JClass("org.mpxj.RelationType")
    ConstraintType = jpype.JClass("org.mpxj.ConstraintType")
    RelationBuilder = jpype.JClass("org.mpxj.Relation$Builder")
    LocalDateTime = jpype.JClass("java.time.LocalDateTime")
    LocalDate = jpype.JClass("java.time.LocalDate")
    Double = jpype.JClass("java.lang.Double")
    File = jpype.JClass("java.io.File")

    project = ProjectFile()
    cal = project.addDefaultBaseCalendar()
    try:
        project.setDefaultCalendar(cal)
    except Exception:
        pass
    for s in doc.get("non_working_dates", []) or []:
        try:
            cal.addCalendarException(LocalDate.parse(s[:10]))
        except Exception:
            pass

    props = project.getProjectProperties()
    props.setName(doc.get("name") or "Programme")
    if doc.get("author"):
        props.setAuthor(doc["author"])
    if doc.get("company"):
        props.setCompany(doc["company"])
    if doc.get("start"):
        props.setStartDate(LocalDateTime.parse(doc["start"][:16]))

    # Resources (one per distinct system/custom resource)
    res_map: Dict[str, Any] = {}
    for t in doc.get("tasks", []):
        for a in t.get("resource_assignments", []) or []:
            key = a.get("resource_id") or f"custom:{a.get('name')}"
            if key not in res_map and a.get("name"):
                r = project.addResource()
                r.setName(a["name"])
                if a.get("type"):
                    r.setGroup(str(a["type"]))
                res_map[key] = r

    # Tasks, honouring the outline
    task_by_uid: Dict[int, Any] = {}
    stack: List[Any] = []  # stack[level-1] = java task
    for t in doc.get("tasks", []):
        level = max(1, int(t.get("outline_level", 1)))
        del stack[level - 1:]
        parent = stack[level - 2] if level >= 2 and len(stack) >= level - 1 else None
        jt = parent.addTask() if parent is not None else project.addTask()
        stack.append(jt)
        jt.setName(t.get("name") or "")
        dur = t.get("duration") or {"value": 1}
        jt.setDuration(Duration.getInstance(float(dur.get("value", 1)), TimeUnit.DAYS))
        if t.get("start"):
            jt.setStart(LocalDateTime.parse(t["start"][:16]))
        if t.get("finish"):
            jt.setFinish(LocalDateTime.parse(t["finish"][:16]))
        if t.get("is_milestone"):
            jt.setMilestone(True)
        pc = t.get("percent_complete")
        if pc:
            jt.setPercentageComplete(Double(float(pc)))
        if t.get("notes"):
            jt.setNotes(t["notes"])
        ct, cd = t.get("constraint_type"), t.get("constraint_date")
        if ct and cd:
            try:
                jt.setConstraintType(ConstraintType.START_NO_EARLIER_THAN if ct == "SNET" else ConstraintType.MUST_START_ON)
                jt.setConstraintDate(LocalDateTime.parse(cd[:10] + "T08:00"))
            except Exception:
                pass
        task_by_uid[t["uid"]] = jt

    for t in doc.get("tasks", []):
        jt = task_by_uid[t["uid"]]
        for p in t.get("predecessors", []) or []:
            pt = task_by_uid.get(p.get("uid"))
            if pt is None:
                continue
            lag = Duration.getInstance(float(p.get("lag_days") or 0), TimeUnit.DAYS)
            jt.addPredecessor(
                RelationBuilder().predecessorTask(pt)
                .type(getattr(RelationType, _REL_FROM.get(p.get("type", "FS"), "FINISH_START")))
                .lag(lag)
            )
        for a in t.get("resource_assignments", []) or []:
            key = a.get("resource_id") or f"custom:{a.get('name')}"
            r = res_map.get(key)
            if r is None:
                continue
            asg = jt.addResourceAssignment(r)
            try:
                asg.setUnits(Double(float(a.get("units") or 1) * 100.0))
            except Exception:
                pass

    Writer().write(project, File(out_path))
    return out_path


# ---------------------------------------------------------------- helper process

class WorkerError(Exception):
    """A readable message for the estimator (never a stack trace)."""


def run_worker(mode: str, inp: str, out: str, timeout: int = 180) -> None:
    """Run parse/export in a separate process so the JVM's memory is returned afterwards."""
    try:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), mode, inp, out], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise WorkerError("Reading the programme took too long. Try saving it as MS Project XML and uploading that.")
    if r.returncode != 0:
        msg = (r.stderr or "").strip().splitlines()
        last = next((m for m in reversed(msg) if m.strip() and not m.startswith("Picked up")), "")
        if "Java is not installed" in (r.stderr or ""):
            raise WorkerError("Java is not installed on the server yet, so MS Project files can't be read or written.")
        raise WorkerError(f"Could not process the programme file: {last[:300] or 'unknown problem'}")


def parse_in_worker(path: str) -> Dict[str, Any]:
    out = path + ".json"
    try:
        run_worker("parse", path, out)
        with open(out) as f:
            return json.load(f)
    finally:
        if os.path.exists(out):
            os.unlink(out)


def export_in_worker(doc: Dict[str, Any], out_xml: str) -> None:
    inp = out_xml + ".in.json"
    try:
        with open(inp, "w") as f:
            json.dump(doc, f)
        run_worker("export", inp, out_xml)
    finally:
        if os.path.exists(inp):
            os.unlink(inp)


if __name__ == "__main__":
    mode, a, b = sys.argv[1:4]
    if mode == "parse":
        with open(b, "w") as f:
            json.dump(parse_file(a), f)
    elif mode == "export":
        with open(a) as f:
            export_xml(json.load(f), b)
    else:
        raise SystemExit(f"unknown mode {mode}")
