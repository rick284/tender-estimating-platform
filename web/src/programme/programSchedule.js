/**
 * Programme scheduling engine (pure functions, no React).
 *
 * Works on a flat list of tasks in MS Project row order:
 *   { uid, id, name, outline_level, duration:{value,unit:'D'}, percent_complete,
 *     predecessors:[{uid,id,type:'FS'|'SS'|'FF'|'SF',lag_days}],
 *     constraint_type: null|'SNET'|'MSO', constraint_date:'YYYY-MM-DD', ... }
 *
 * Scheduling is critical-path on whole WORKING days. A "boundary" b is the
 * start of the b-th working day: ES = b, EF = ES + duration, so a 3-day task
 * starting on working day 0 has ES 0, EF 3 and finishes at the end of day 2.
 * Summary rows are derived from the outline (a row followed by a deeper row)
 * and roll up their leaf descendants; links to/from a summary apply to all of
 * its leaf descendants.
 */

const DAY_MS = 86400000;
const pad = (n) => String(n).padStart(2, '0');

export const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parseYmd = (s) => {
  if (!s) return null;
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
};
const addDaysD = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const dayDiff = (a, b) => Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / DAY_MS);

// ---------------------------------------------------------------- calendar

export function makeCalendar({ origin, working_days = [true, true, true, true, true, false, false], non_working_dates = [], horizonDays = 3650 }) {
  const off = new Set(non_working_dates.map((s) => String(s).slice(0, 10)));
  const wdOffsets = []; // calendar-day offset of each working day
  const cum = new Array(horizonDays + 1); // cum[k] = # working days in [0,k)
  let count = 0;
  for (let k = 0; k < horizonDays; k++) {
    cum[k] = count;
    const d = addDaysD(origin, k);
    const mon0 = (d.getDay() + 6) % 7;
    if (working_days[mon0] && !off.has(ymd(d))) {
      wdOffsets.push(k);
      count++;
    }
  }
  cum[horizonDays] = count;
  return {
    origin,
    working_days,
    isWorking(d) {
      const k = dayDiff(origin, d);
      if (k < 0 || k >= horizonDays) return working_days[(d.getDay() + 6) % 7];
      return cum[k + 1] > cum[k];
    },
    /** boundary (working-day index) of a calendar date; non-working dates map to the next working day */
    boundary(d) {
      const k = Math.max(0, Math.min(horizonDays, dayDiff(origin, d)));
      return cum[k];
    },
    /** calendar date of the start of working day b */
    dateOf(b) {
      const i = Math.max(0, Math.min(wdOffsets.length - 1, b));
      return addDaysD(origin, wdOffsets[i]);
    },
    /** working days in the inclusive calendar range [a, b] */
    workingDaysBetween(a, b) {
      return this.boundary(addDaysD(b, 1)) - this.boundary(a);
    },
  };
}

export function calendarFor(data, tasks) {
  // Boundary 0 is the project start, so the origin must be the project start date
  let origin = parseYmd(data.start);
  if (!origin) {
    (tasks || data.tasks || []).forEach((t) => {
      const d = parseYmd(t.start);
      if (d && (!origin || d < origin)) origin = d;
    });
  }
  if (!origin) origin = new Date();
  return makeCalendar({ origin, working_days: data.working_days, non_working_dates: data.non_working_dates || [] });
}

// ---------------------------------------------------------------- helpers

export const durDays = (t) => (t.duration ? Number(t.duration.value) || 0 : 0);

/** Fill uid on tasks and predecessor uid from row id (older saved docs only have row ids). */
export function ensureUids(tasks) {
  const byId = new Map();
  let maxUid = 0;
  tasks.forEach((t) => {
    if (t.uid != null) maxUid = Math.max(maxUid, t.uid);
  });
  const out = tasks.map((t) => {
    const uid = t.uid != null ? t.uid : ++maxUid;
    byId.set(t.id, uid);
    return { ...t, uid };
  });
  return out.map((t) => ({
    ...t,
    predecessors: (t.predecessors || []).map((p) => ({ ...p, uid: p.uid != null ? p.uid : byId.get(p.id) })).filter((p) => p.uid != null),
  }));
}

export function isSummaryAt(tasks, i) {
  return i + 1 < tasks.length && tasks[i + 1].outline_level > tasks[i].outline_level;
}

/** Row numbers, WBS and predecessor row ids from structure. */
export function renumber(tasks) {
  const uidToId = new Map(tasks.map((t, i) => [t.uid, i + 1]));
  const counters = [];
  return tasks.map((t, i) => {
    const lvl = t.outline_level;
    counters.length = lvl;
    for (let k = 0; k < lvl; k++) if (counters[k] == null) counters[k] = 0;
    counters[lvl - 1] += 1;
    const wbs = counters.slice(0, lvl).join('.');
    let parent_id = null;
    for (let j = i - 1; j >= 0; j--) {
      if (tasks[j].outline_level < lvl) {
        parent_id = j + 1;
        break;
      }
    }
    return {
      ...t,
      id: i + 1,
      wbs,
      parent_id,
      is_summary: isSummaryAt(tasks, i),
      predecessors: (t.predecessors || []).filter((p) => uidToId.has(p.uid)).map((p) => ({ ...p, id: uidToId.get(p.uid) })),
    };
  });
}

function leafIndexesUnder(tasks, i) {
  const out = [];
  const lvl = tasks[i].outline_level;
  for (let j = i + 1; j < tasks.length && tasks[j].outline_level > lvl; j++) {
    if (!isSummaryAt(tasks, j)) out.push(j);
  }
  return out;
}

// ---------------------------------------------------------------- scheduling

/**
 * Schedule `tasks`. Returns { tasks, error } where error is
 * { type:'cycle', uids:[...] } if the links are circular (tasks then unchanged).
 */
export function schedule(tasks, cal) {
  const n = tasks.length;
  const idxByUid = new Map(tasks.map((t, i) => [t.uid, i]));
  const summary = tasks.map((_, i) => isSummaryAt(tasks, i));
  const leaves = [];
  tasks.forEach((_, i) => {
    if (!summary[i]) leaves.push(i);
  });

  const sources = (uid) => {
    const i = idxByUid.get(uid);
    if (i == null) return [];
    return summary[i] ? leafIndexesUnder(tasks, i) : [i];
  };

  // edges src -> tgt between leaves
  const edges = []; // {s, t, type, lag}
  tasks.forEach((t, ti) => {
    const targets = summary[ti] ? leafIndexesUnder(tasks, ti) : [ti];
    (t.predecessors || []).forEach((p) => {
      sources(p.uid).forEach((s) => {
        targets.forEach((tg) => {
          if (s !== tg) edges.push({ s, t: tg, type: p.type || 'FS', lag: Number(p.lag_days) || 0 });
        });
      });
    });
  });

  const inE = new Map();
  const outE = new Map();
  edges.forEach((e) => {
    if (!inE.has(e.t)) inE.set(e.t, []);
    if (!outE.has(e.s)) outE.set(e.s, []);
    inE.get(e.t).push(e);
    outE.get(e.s).push(e);
  });

  // topological order (Kahn) over leaves
  const indeg = new Map(leaves.map((i) => [i, (inE.get(i) || []).length]));
  const queue = leaves.filter((i) => indeg.get(i) === 0);
  const order = [];
  while (queue.length) {
    const i = queue.shift();
    order.push(i);
    (outE.get(i) || []).forEach((e) => {
      indeg.set(e.t, indeg.get(e.t) - 1);
      if (indeg.get(e.t) === 0) queue.push(e.t);
    });
  }
  if (order.length !== leaves.length) {
    const stuck = leaves.filter((i) => !order.includes(i)).map((i) => tasks[i].uid);
    return { tasks, error: { type: 'cycle', uids: stuck } };
  }

  // forward pass
  const ES = new Array(n).fill(0);
  const EF = new Array(n).fill(0);
  const D = tasks.map((t) => Math.max(0, Math.round(durDays(t))));
  order.forEach((i) => {
    const t = tasks[i];
    let es = 0;
    if (t.constraint_type === 'SNET' && t.constraint_date) es = Math.max(es, cal.boundary(parseYmd(t.constraint_date)));
    (inE.get(i) || []).forEach((e) => {
      if (e.type === 'FS') es = Math.max(es, EF[e.s] + e.lag);
      else if (e.type === 'SS') es = Math.max(es, ES[e.s] + e.lag);
      else if (e.type === 'FF') es = Math.max(es, EF[e.s] + e.lag - D[i]);
      else if (e.type === 'SF') es = Math.max(es, ES[e.s] + e.lag - D[i]);
    });
    if (t.constraint_type === 'MSO' && t.constraint_date) es = cal.boundary(parseYmd(t.constraint_date));
    ES[i] = Math.max(0, es);
    EF[i] = ES[i] + D[i];
  });

  // backward pass
  const projEF = leaves.reduce((m, i) => Math.max(m, EF[i]), 0);
  const LF = new Array(n).fill(projEF);
  const LS = new Array(n).fill(0);
  [...order].reverse().forEach((i) => {
    let lf = projEF;
    (outE.get(i) || []).forEach((e) => {
      const succLS = LS[e.t];
      const succLF = LF[e.t];
      if (e.type === 'FS') lf = Math.min(lf, succLS - e.lag);
      else if (e.type === 'SS') lf = Math.min(lf, succLS - e.lag + D[i]);
      else if (e.type === 'FF') lf = Math.min(lf, succLF - e.lag);
      else if (e.type === 'SF') lf = Math.min(lf, succLF - e.lag + D[i]);
    });
    LF[i] = lf;
    LS[i] = lf - D[i];
  });

  // rollups
  const out = tasks.map((t) => ({ ...t }));
  const FLOAT = new Array(n).fill(0);
  leaves.forEach((i) => {
    FLOAT[i] = LS[i] - ES[i];
  });

  const fmtStart = (b) => `${ymd(cal.dateOf(b))}T08:00`;
  const fmtFinish = (efb) => `${ymd(cal.dateOf(Math.max(0, efb - 1)))}T17:00`;
  const fmtMilestone = (b) => (b > 0 ? `${ymd(cal.dateOf(b - 1))}T17:00` : `${ymd(cal.dateOf(0))}T08:00`);

  leaves.forEach((i) => {
    const t = out[i];
    if (D[i] === 0) {
      t.is_milestone = true;
      t.start = fmtMilestone(ES[i]);
      t.finish = t.start;
    } else {
      t.is_milestone = false;
      t.start = fmtStart(ES[i]);
      t.finish = fmtFinish(EF[i]);
    }
    t.duration = { value: D[i], unit: 'D' };
    t.total_slack = { value: FLOAT[i], unit: 'D' };
    t.is_critical = FLOAT[i] <= 0;
    t.is_summary = false;
  });

  // summaries bottom-up (process deepest rows first)
  for (let i = n - 1; i >= 0; i--) {
    if (!summary[i]) continue;
    const kids = leafIndexesUnder(tasks, i);
    const t = out[i];
    t.is_summary = true;
    t.is_milestone = false;
    if (!kids.length) continue;
    const es = Math.min(...kids.map((k) => ES[k]));
    const ef = Math.max(...kids.map((k) => EF[k]));
    t.start = fmtStart(es);
    t.finish = fmtFinish(Math.max(ef, es + 1));
    t.duration = { value: Math.max(0, ef - es), unit: 'D' };
    t.is_critical = kids.some((k) => FLOAT[k] <= 0);
    t.total_slack = { value: Math.min(...kids.map((k) => FLOAT[k])), unit: 'D' };
    const wsum = kids.reduce((a, k) => a + D[k], 0);
    t.percent_complete = wsum > 0 ? Math.round(kids.reduce((a, k) => a + D[k] * (out[k].percent_complete || 0), 0) / wsum) : 0;
  }

  return { tasks: out, error: null };
}

/**
 * Take a programme as parsed from MS Project and make it re-schedulable
 * without moving anything: wherever our ASAP result differs from MS Project's
 * stored start, pin that task with SNET (stored later) or MSO (stored earlier).
 */
export function normalizeImported(rawTasks, cal) {
  let tasks = renumber(ensureUids(rawTasks)).map((t) => ({ ...t, constraint_type: null, constraint_date: null }));
  const stored = new Map(rawTasks.map((t, i) => [ensureUids(rawTasks)[i].uid, t]));
  for (let guard = 0; guard < tasks.length + 5; guard++) {
    const res = schedule(tasks, cal);
    if (res.error) return { tasks: ensureUids(rawTasks), error: res.error };
    let fixed = false;
    const sorted = res.tasks
      .map((t, i) => ({ t, i }))
      .filter(({ t }) => !t.is_summary)
      .sort((a, b) => a.t.start.localeCompare(b.t.start));
    for (const { t, i } of sorted) {
      const src = stored.get(t.uid);
      if (!src || !src.start) continue;
      const want = cal.boundary(parseYmd(src.start));
      const got = cal.boundary(parseYmd(t.start));
      const isMs = durDays(t) === 0;
      if (isMs) continue;
      if (want !== got) {
        tasks[i] = {
          ...tasks[i],
          constraint_type: want > got ? 'SNET' : 'MSO',
          constraint_date: ymd(parseYmd(src.start)),
        };
        fixed = true;
        break;
      }
    }
    if (!fixed) return { tasks: res.tasks, error: null };
  }
  return { tasks: schedule(tasks, cal).tasks, error: null };
}

// ---------------------------------------------------------------- predecessor text

const REL = /^\s*(\d+)\s*(FS|SS|FF|SF)?\s*(?:([+-])\s*(\d+(?:\.\d+)?)\s*(?:d|day|days)?)?\s*$/i;

export function formatPreds(t) {
  return (t.predecessors || [])
    .map((p) => `${p.id}${p.type === 'FS' && !p.lag_days ? '' : p.type || 'FS'}${p.lag_days ? (p.lag_days > 0 ? '+' : '-') + Math.abs(p.lag_days) + 'd' : ''}`)
    .join(', ');
}

/** Parse "5, 7SS+2d, 9FF-1d" (row ids) into predecessor links. */
export function parsePreds(text, tasks, selfIndex) {
  const preds = [];
  const t = String(text || '').trim();
  if (!t) return { preds, error: null };
  for (const part of t.split(/[,;]/)) {
    if (!part.trim()) continue;
    const m = part.match(REL);
    if (!m) return { preds: null, error: `Can't read "${part.trim()}" - use e.g. 5, 7SS+2d` };
    const id = Number(m[1]);
    const idx = id - 1;
    if (idx < 0 || idx >= tasks.length) return { preds: null, error: `No task with ID ${id}` };
    if (idx === selfIndex) return { preds: null, error: 'A task cannot depend on itself' };
    const lag = m[3] ? (m[3] === '-' ? -1 : 1) * Number(m[4]) : 0;
    preds.push({ uid: tasks[idx].uid, id, type: (m[2] || 'FS').toUpperCase(), lag_days: lag });
  }
  return { preds, error: null };
}

// ---------------------------------------------------------------- structure operations
// All return a new renumbered task array; callers re-run schedule() afterwards.

const nextUid = (tasks) => tasks.reduce((m, t) => Math.max(m, t.uid || 0), 0) + 1;

export function blankTask(tasks, props = {}) {
  return {
    uid: nextUid(tasks),
    name: 'New task',
    outline_level: 1,
    duration: { value: 1, unit: 'D' },
    percent_complete: 0,
    predecessors: [],
    resources: [],
    resource_assignments: [],
    constraint_type: null,
    constraint_date: null,
    notes: '',
    is_active: true,
    ...props,
  };
}

export function insertTask(tasks, afterIndex, props = {}) {
  const level = afterIndex >= 0 ? tasks[afterIndex].outline_level : 1;
  // insert after the whole subtree of the anchor
  let at = afterIndex + 1;
  if (afterIndex >= 0) while (at < tasks.length && tasks[at].outline_level > level) at++;
  const t = blankTask(tasks, { outline_level: level, ...props });
  const out = [...tasks.slice(0, at), t, ...tasks.slice(at)];
  return { tasks: renumber(out), index: at };
}

export function subtreeEnd(tasks, i) {
  let j = i + 1;
  while (j < tasks.length && tasks[j].outline_level > tasks[i].outline_level) j++;
  return j; // exclusive
}

export function deleteTask(tasks, i) {
  const end = subtreeEnd(tasks, i);
  const gone = new Set(tasks.slice(i, end).map((t) => t.uid));
  const out = [...tasks.slice(0, i), ...tasks.slice(end)].map((t) => ({
    ...t,
    predecessors: (t.predecessors || []).filter((p) => !gone.has(p.uid)),
  }));
  return renumber(out);
}

export function indentTask(tasks, i) {
  if (i <= 0 || tasks[i].outline_level > tasks[i - 1].outline_level) return tasks;
  const end = subtreeEnd(tasks, i);
  return renumber(tasks.map((t, k) => (k >= i && k < end ? { ...t, outline_level: t.outline_level + 1 } : t)));
}

export function outdentTask(tasks, i) {
  if (tasks[i].outline_level <= 1) return tasks;
  const end = subtreeEnd(tasks, i);
  return renumber(tasks.map((t, k) => (k >= i && k < end ? { ...t, outline_level: t.outline_level - 1 } : t)));
}

/** Move a task (with its children) up or down past its neighbouring sibling. Returns {tasks,index}. */
export function moveTask(tasks, i, dir) {
  const end = subtreeEnd(tasks, i);
  const lvl = tasks[i].outline_level;
  if (dir < 0) {
    let p = i - 1;
    while (p >= 0 && tasks[p].outline_level > lvl) p--;
    if (p < 0 || tasks[p].outline_level < lvl) return { tasks, index: i };
    const out = [...tasks.slice(0, p), ...tasks.slice(i, end), ...tasks.slice(p, i), ...tasks.slice(end)];
    return { tasks: renumber(out), index: p };
  }
  if (end >= tasks.length || tasks[end].outline_level < lvl) return { tasks, index: i };
  const nEnd = subtreeEnd(tasks, end);
  const out = [...tasks.slice(0, i), ...tasks.slice(end, nEnd), ...tasks.slice(i, end), ...tasks.slice(nEnd)];
  return { tasks: renumber(out), index: i + (nEnd - end) };
}

/** True if adding "pred -> task" would create a loop. */
export function wouldCycle(tasks, cal, taskUid, predUid) {
  const idx = tasks.findIndex((t) => t.uid === taskUid);
  if (idx < 0) return false;
  const trial = tasks.map((t, i) => (i === idx ? { ...t, predecessors: [...(t.predecessors || []), { uid: predUid, type: 'FS', lag_days: 0 }] } : t));
  return !!schedule(trial, cal).error;
}

// ---------------------------------------------------------------- resources

/** Per-resource usage: total unit-days, peak concurrent units, task count. */
export function resourceUsage(tasks, cal) {
  const map = new Map();
  tasks.forEach((t) => {
    if (t.is_summary) return;
    const d = Math.max(0, Math.round(durDays(t)));
    const es = t.start ? cal.boundary(parseYmd(t.start)) : 0;
    (t.resource_assignments || []).forEach((a) => {
      const key = a.resource_id || `custom:${a.name}`;
      if (!map.has(key)) map.set(key, { key, name: a.name, type: a.type, custom: !a.resource_id, unit: a.unit, tasks: 0, unitDays: 0, perDay: new Map() });
      const r = map.get(key);
      r.tasks += 1;
      r.unitDays += (Number(a.units) || 0) * d;
      for (let b = es; b < es + d; b++) r.perDay.set(b, (r.perDay.get(b) || 0) + (Number(a.units) || 0));
    });
  });
  return [...map.values()]
    .map((r) => ({ ...r, peak: Math.max(0, ...r.perDay.values()) }))
    .sort((a, b) => b.unitDays - a.unitDays);
}
