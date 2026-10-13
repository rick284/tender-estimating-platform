import React, { useMemo, useState, useRef, useLayoutEffect, useEffect } from 'react';
import { ChevronRight, ChevronDown, Pin, Users, Link2 } from 'lucide-react';
import { formatPreds, parsePreds, ymd } from './programSchedule';

/**
 * MS Project style Gantt: task table on the left, timeline on the right.
 *
 * View mode: just pass `data` (parsed snapshot). Edit mode: also pass
 *   editable, tasks (scheduled), cal, selectedUid, onSelect(uid),
 *   onEdit(uid, patch), onLink(fromUid, toUid), onOpenResources(uid), onError(msg)
 * The parent owns state; every change goes back through onEdit/onLink.
 */

const ROW_H = 24;
const HEAD_H = 44;
const DAY_MS = 86400000;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DOW = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const DOW_LONG = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const ZOOMS = { day: 26, week: 9, month: 2.6 };
const MIN_PX = 1.2, MAX_PX = 90, ZOOM_STEP = 1.3;

const COLORS = {
  normal: '#4472C4',
  normalDone: '#1F3864',
  critical: '#E53935',
  criticalDone: '#7F1D1D',
  summary: '#111827',
  baseline: '#9CA3AF',
  link: '#374151',
};

const parse = (s) => (s ? new Date(s) : null);
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const dayDiff = (a, b) => Math.round((startOfDay(b) - startOfDay(a)) / DAY_MS);
const fmtDate = (s) => {
  const d = parse(s);
  if (!d) return '';
  return `${DOW_LONG[d.getDay()]} ${d.getDate()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getFullYear()).slice(2)}`;
};
const UNIT = { D: 'day', H: 'hr', W: 'wk', M: 'mon', Y: 'yr', MIN: 'min', ED: 'eday', EW: 'ewk', EM: 'emon', PERCENT: '%' };
const fmtDuration = (d, milestone) => {
  if (milestone) return '0 days';
  if (!d) return '';
  const unit = UNIT[d.unit] || String(d.unit).toLowerCase();
  const v = Math.round(d.value * 100) / 100;
  return `${v} ${unit}${v === 1 ? '' : 's'}`;
};

const NAME_GUTTER = 16; // width reserved for the collapse arrow
const CONSTRAINT_LABEL = { SNET: 'Start no earlier than', MSO: 'Fixed start' };
const key = (t) => t.uid ?? t.id;

/** Table cell input: commits on blur / Enter, reverts on Escape. */
const CellInput = ({ value, onCommit, type = 'text', className = '', dataAttr, ...rest }) => {
  const [draft, setDraft] = useState(String(value ?? ''));
  const editing = useRef(false);
  useEffect(() => {
    if (!editing.current) setDraft(String(value ?? ''));
  }, [value]);
  const finish = (commit) => {
    editing.current = false;
    if (commit && draft !== String(value ?? '')) onCommit(draft);
    // show the stored value again; if the edit was accepted the value prop changes and the effect below takes over
    setDraft(String(value ?? ''));
  };
  return (
    <input
      {...rest}
      {...(dataAttr || {})}
      type={type}
      value={draft}
      onFocus={() => { editing.current = true; }}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => finish(true)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); }
        else if (e.key === 'Escape') { e.preventDefault(); setDraft(String(value ?? '')); editing.current = false; e.currentTarget.blur(); }
        e.stopPropagation();
      }}
      className={`bg-transparent border-0 hover:bg-muted focus:bg-background focus:ring-1 focus:ring-primary px-0 -ml-px h-[20px] w-full min-w-0 text-xs outline-none rounded-sm ${className}`}
    />
  );
};

const ProgramGantt = ({
  data,
  tasks: tasksProp,
  cal,
  editable = false,
  selectedUid: selectedProp,
  selectedUids: selectedUidsProp,
  onSelect,
  onEdit,
  onLink,
  onOpenResources,
  onOpenLinks,
  onError,
}) => {
  const tasks = tasksProp || data.tasks;
  const [zoom, setZoom] = useState('day');
  const [pxPerDay, setPxPerDay] = useState(ZOOMS.day);
  const [collapsed, setCollapsed] = useState(() => new Set());
  const [showBaseline, setShowBaseline] = useState(true);
  const [showLinks, setShowLinks] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  // Which table columns are hidden (remembered on this computer). Task Name can't be hidden.
  const [hiddenCols, setHiddenCols] = useState(() => {
    try { const v = JSON.parse(localStorage.getItem('qsi.gantt.hiddenCols') || '[]'); return Array.isArray(v) ? v.filter((x) => x !== 'name') : []; } catch { return []; }
  });
  const [colMenu, setColMenu] = useState(false);
  const toggleCol = (key) => setHiddenCols((cur) => {
    const next = cur.includes(key) ? cur.filter((x) => x !== key) : [...cur, key];
    try { localStorage.setItem('qsi.gantt.hiddenCols', JSON.stringify(next)); } catch { /* private mode */ }
    return next;
  });
  const [localSel, setLocalSel] = useState(null);
  const [colWidths, setColWidths] = useState({}); // user-resized table columns, by key
  const [paneW, setPaneW] = useState(null); // visible width of the table pane (drag the divider)
  const [drag, setDrag] = useState(null); // {uid, mode, dx}
  const [linking, setLinking] = useState(null); // {fromUid, x, y}
  const bodyRef = useRef(null);
  const leftInnerRef = useRef(null);
  const rightInnerRef = useRef(null);
  const leftBarRef = useRef(null);
  const rightBarRef = useRef(null);
  const svgRef = useRef(null);
  const viewportW = useRef(1000);

  const selected = selectedProp !== undefined ? selectedProp : localSel;
  const select = (uid, opts) => (onSelect ? onSelect(uid, opts) : setLocalSel(uid));
  const selectedSet = useMemo(() => new Set(selectedUidsProp || (selected != null ? [selected] : [])), [selectedUidsProp, selected]);

  useLayoutEffect(() => {
    if (rightBarRef.current) viewportW.current = rightBarRef.current.clientWidth;
  }, []);

  useEffect(() => { setColWidths({}); setPaneW(null); }, [editable, hiddenCols]);

  // Timeline range
  const range = useMemo(() => {
    let min = null;
    let max = null;
    const consider = (s) => {
      const d = parse(s);
      if (!d) return;
      if (!min || d < min) min = d;
      if (!max || d > max) max = d;
    };
    tasks.forEach((t) => {
      consider(t.start);
      consider(t.finish);
      consider(t.baseline_start);
      consider(t.baseline_finish);
    });
    consider(data.start);
    consider(data.finish);
    if (!min) min = new Date();
    if (!max) max = addDays(min, 30);
    let origin = addDays(startOfDay(min), -7);
    origin = addDays(origin, -((origin.getDay() + 6) % 7));
    const end = addDays(startOfDay(max), editable ? 60 : 21);
    return { origin, days: dayDiff(origin, end) + 1 };
  }, [tasks, data.start, data.finish, editable]);

  const rows = useMemo(() => {
    const out = [];
    let hideBelow = null;
    tasks.forEach((t) => {
      if (hideBelow !== null) {
        if (t.outline_level > hideBelow) return;
        hideBelow = null;
      }
      out.push(t);
      if (t.is_summary && collapsed.has(key(t))) hideBelow = t.outline_level;
    });
    return out;
  }, [tasks, collapsed]);

  const rowIndex = useMemo(() => {
    const m = new Map();
    rows.forEach((t, i) => m.set(key(t), i));
    return m;
  }, [rows]);

  const x = (date, edge) => {
    const d = parse(date);
    const base = dayDiff(range.origin, d) * pxPerDay;
    if (edge === 'start') return base;
    if (edge === 'end') return base + pxPerDay;
    return base + (d.getHours() >= 12 ? pxPerDay : 0);
  };

  const dragShift = (t) => (drag && drag.uid === key(t) ? Math.round(drag.dx / pxPerDay) * pxPerDay : 0);

  const geom = (t) => {
    if (!t.start || !t.finish) return null;
    const shift = dragShift(t);
    const isDragged = drag && drag.uid === key(t);
    if (t.is_milestone) {
      const cx = x(t.finish, 'mid') + (isDragged && drag.mode === 'move' ? shift : 0);
      return { x1: cx, x2: cx };
    }
    let x1 = x(t.start, 'start');
    let x2 = Math.max(x(t.finish, 'end'), x1 + 2);
    if (isDragged && drag.mode === 'move') { x1 += shift; x2 += shift; }
    if (isDragged && drag.mode === 'resize') x2 = Math.max(x1 + pxPerDay, x2 + shift);
    return { x1, x2 };
  };

  const toggle = (id) =>
    setCollapsed((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const expandAll = () => setCollapsed(new Set());
  const collapseAll = () => setCollapsed(new Set(tasks.filter((t) => t.is_summary).map(key)));

  const setZoomLevel = (z) => { setZoom(z); setPxPerDay(ZOOMS[z]); };
  // Zoom in / out in steps, keeping the date in the middle of the chart where it is
  const pendingScroll = useRef(null);
  const zoomBy = (factor) => {
    const next = Math.min(MAX_PX, Math.max(MIN_PX, pxPerDay * factor));
    if (next === pxPerDay) return;
    const bar = rightBarRef.current;
    if (bar) pendingScroll.current = Math.max(0, (bar.scrollLeft + bar.clientWidth / 2) * (next / pxPerDay) - bar.clientWidth / 2);
    setZoom('custom');
    setPxPerDay(next);
  };
  useLayoutEffect(() => {
    if (pendingScroll.current !== null && rightBarRef.current) { rightBarRef.current.scrollLeft = pendingScroll.current; pendingScroll.current = null; }
  }, [pxPerDay]);
  const fit = () => {
    const w = (rightBarRef.current?.clientWidth || viewportW.current) - 24;
    setZoom('fit');
    setPxPerDay(Math.max(1.2, w / range.days));
  };

  const totalW = range.days * pxPerDay;
  const bodyH = Math.max(rows.length * ROW_H, ROW_H);

  // Header tiers
  const header = useMemo(() => {
    const top = [];
    const bottom = [];
    const showDays = pxPerDay >= 18;
    const showWeeks = pxPerDay >= 5;
    let i = 0;
    while (i < range.days) {
      const d = addDays(range.origin, i);
      if (showDays) {
        const mondayOffset = (d.getDay() + 6) % 7;
        const span = Math.min(7 - mondayOffset, range.days - i);
        top.push({ left: i * pxPerDay, width: span * pxPerDay, label: `${d.getDate()} ${MONTHS[d.getMonth()]} '${String(d.getFullYear()).slice(2)}` });
        i += span;
      } else {
        const next = new Date(d.getFullYear(), d.getMonth() + 1, 1);
        const span = Math.min(dayDiff(d, next), range.days - i);
        top.push({ left: i * pxPerDay, width: span * pxPerDay, label: `${MONTHS[d.getMonth()]} ${d.getFullYear()}` });
        i += span;
      }
    }
    if (showDays) {
      for (let k = 0; k < range.days; k++) {
        const d = addDays(range.origin, k);
        bottom.push({ left: k * pxPerDay, width: pxPerDay, label: DOW[d.getDay()] });
      }
    } else if (showWeeks) {
      for (let k = 0; k < range.days; k += 7) {
        const d = addDays(range.origin, k);
        bottom.push({ left: k * pxPerDay, width: 7 * pxPerDay, label: String(d.getDate()) });
      }
    } else {
      for (let k = 0; k < range.days; ) {
        const d = addDays(range.origin, k);
        const next = new Date(d.getFullYear(), d.getMonth() + 1, 1);
        const span = Math.min(dayDiff(d, next), range.days - k);
        bottom.push({ left: k * pxPerDay, width: span * pxPerDay, label: MONTHS[d.getMonth()].slice(0, 1) });
        k += span;
      }
    }
    return { top, bottom };
  }, [range, pxPerDay]);

  const nonWorkingSet = useMemo(() => new Set((data.non_working_dates || []).map((s) => String(s).slice(0, 10))), [data.non_working_dates]);
  const shading = useMemo(() => {
    if (pxPerDay < 6) return [];
    const wd = data.working_days || [true, true, true, true, true, false, false];
    const out = [];
    for (let k = 0; k < range.days; k++) {
      const d = addDays(range.origin, k);
      if (!wd[(d.getDay() + 6) % 7] || nonWorkingSet.has(ymd(d))) out.push(k);
    }
    return out;
  }, [range, pxPerDay, data.working_days, nonWorkingSet]);

  const today = startOfDay(new Date());
  const todayX = dayDiff(range.origin, today) * pxPerDay + pxPerDay / 2;
  const showToday = todayX > 0 && todayX < totalW;
  const status = parse(data.status_date);
  const statusX = status ? dayDiff(range.origin, status) * pxPerDay + pxPerDay : null;

  // Dependency links
  const links = useMemo(() => {
    if (!showLinks) return [];
    const out = [];
    const byUid = new Map(tasks.map((t) => [key(t), t]));
    rows.forEach((t, ri) => {
      const g = geom(t);
      if (!g) return;
      (t.predecessors || []).forEach((p) => {
        const pk = p.uid ?? p.id;
        const pi = rowIndex.get(pk);
        const pt = byUid.get(pk);
        if (pi === undefined || !pt) return;
        const pg = geom(pt);
        if (!pg) return;
        const fromEnd = p.type === 'FS' || p.type === 'FF';
        const toStart = p.type === 'FS' || p.type === 'SS';
        const x1 = fromEnd ? pg.x2 : pg.x1;
        const x2 = toStart ? g.x1 : g.x2;
        const y1 = pi * ROW_H + ROW_H / 2;
        const y2 = ri * ROW_H + ROW_H / 2;
        const down = y2 > y1;
        const exitDir = fromEnd ? 1 : -1;
        const enterDir = toStart ? 1 : -1;
        const gap = 8;
        let d;
        if (p.type === 'FS' && x2 >= x1 + gap + 4) {
          d = `M${x1},${y1} H${x1 + gap} V${y2} H${x2 - 1}`;
        } else {
          const xa = x1 + exitDir * gap;
          const xb = x2 - enterDir * gap;
          const yMid = down ? pi * ROW_H + ROW_H - 1 : pi * ROW_H + 1;
          d = `M${x1},${y1} H${xa} V${yMid} H${xb} V${y2} H${x2 - enterDir}`;
        }
        out.push({ key: `${pk}-${key(t)}`, d, hot: selected === key(t) || selected === pk });
      });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, rowIndex, tasks, pxPerDay, showLinks, selected, range, drag]);

  // ---------------------------------------------------------- drag + link handlers

  const svgPoint = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const snapWorking = (d) => {
    if (!cal) return d;
    let cur = d;
    for (let i = 0; i < 14 && !cal.isWorking(cur); i++) cur = addDays(cur, 1);
    return cur;
  };

  const startBarDrag = (e, t, mode) => {
    if (!editable || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    select(key(t));
    const startX = e.clientX;
    const uid = key(t);
    let dx = 0;
    setDrag({ uid, mode, dx: 0 });
    const move = (ev) => {
      dx = ev.clientX - startX;
      setDrag({ uid, mode, dx });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      setDrag(null);
      const days = Math.round(dx / pxPerDay);
      if (!days) return;
      if (mode === 'move') {
        const newStart = snapWorking(addDays(parse(t.start), days));
        const type = t.constraint_type === 'MSO' ? 'MSO' : 'SNET';
        if (onEdit) onEdit(uid, { constraint_type: type, constraint_date: ymd(newStart) });
      } else if (cal) {
        const newFinish = addDays(parse(t.finish), days);
        const n = cal.workingDaysBetween(startOfDay(parse(t.start)), newFinish);
        if (onEdit) onEdit(uid, { duration: { value: Math.max(1, n), unit: 'D' } });
      }
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const startLinkDrag = (e, t) => {
    if (!editable || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const fromUid = key(t);
    const p0 = svgPoint(e);
    setLinking({ fromUid, x: p0.x, y: p0.y });
    const move = (ev) => {
      const p = svgPoint(ev);
      setLinking({ fromUid, x: p.x, y: p.y });
    };
    const up = (ev) => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      const p = svgPoint(ev);
      setLinking(null);
      const target = rows[Math.floor(p.y / ROW_H)];
      if (target && key(target) !== fromUid && onLink) onLink(fromUid, key(target));
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  // ---------------------------------------------------------- bars

  const assignmentNames = (t) =>
    t.resource_assignments && t.resource_assignments.length
      ? t.resource_assignments.map((a) => (Number(a.units) > 1 ? `${a.name} x${a.units}` : a.name))
      : t.resources || [];

  const renderBar = (t, i) => {
    const g = geom(t);
    if (!g) return null;
    const y = i * ROW_H;
    const k = key(t);
    const title = `${t.id}. ${t.name}\n${fmtDate(t.start)} → ${fmtDate(t.finish)}\n${fmtDuration(t.duration, t.is_milestone)}  ·  ${t.percent_complete}% complete${t.is_critical ? '  ·  Critical' : ''}${t.constraint_type ? `\n${CONSTRAINT_LABEL[t.constraint_type] || t.constraint_type}: ${t.constraint_date || ''}` : ''}`;
    const dim = t.is_active === false ? 0.45 : 1;
    const names = assignmentNames(t);
    const label = showLabels && names.length ? names.join(', ') : '';
    const pct = Math.max(0, Math.min(100, t.percent_complete || 0)) / 100;
    const canEdit = editable && !t.is_summary;

    let baseline = null;
    if (showBaseline && t.baseline_start && t.baseline_finish && !t.is_milestone) {
      const bx1 = x(t.baseline_start, 'start');
      const bx2 = Math.max(x(t.baseline_finish, 'end'), bx1 + 2);
      baseline = <rect x={bx1} y={y + ROW_H - 8} width={bx2 - bx1} height={4} fill={COLORS.baseline} />;
    }
    const handle = (cx) =>
      canEdit && selected === k && (
        <circle
          cx={cx} cy={y + ROW_H / 2} r={4.5} fill="#fff" stroke="#2563eb" strokeWidth={1.5}
          style={{ cursor: 'crosshair' }} onPointerDown={(e) => startLinkDrag(e, t)} data-link-handle={k}
        >
          <title>Drag onto another task to make it depend on this one</title>
        </circle>
      );

    if (t.is_milestone) {
      const s = 8;
      const cy = y + ROW_H / 2;
      return (
        <g key={k} opacity={dim}>
          <title>{title}</title>
          <polygon
            points={`${g.x1},${cy - s} ${g.x1 + s},${cy} ${g.x1},${cy + s} ${g.x1 - s},${cy}`}
            fill={t.is_critical ? COLORS.critical : COLORS.summary}
            style={canEdit ? { cursor: 'grab' } : undefined}
            onPointerDown={canEdit ? (e) => startBarDrag(e, t, 'move') : undefined}
          />
          {showLabels && !drag && (
            <text x={g.x1 + s + 5} y={cy + 4} fontSize="11" fill="#374151" pointerEvents="none">
              {names.length ? names.join(', ') : fmtDate(t.finish).split(' ')[1]}
            </text>
          )}
          {handle(g.x1 + s + 9)}
        </g>
      );
    }

    if (t.is_summary) {
      const by = y + 6;
      const w = g.x2 - g.x1;
      return (
        <g key={k} opacity={dim}>
          <title>{title}</title>
          {baseline}
          <rect x={g.x1} y={by} width={w} height={6} fill={COLORS.summary} />
          {t.percent_complete > 0 && <rect x={g.x1} y={by + 2} width={w * pct} height={2} fill="#9CA3AF" />}
          <polygon points={`${g.x1},${by + 6} ${g.x1 + 7},${by + 6} ${g.x1},${by + 13}`} fill={COLORS.summary} />
          <polygon points={`${g.x2},${by + 6} ${g.x2 - 7},${by + 6} ${g.x2},${by + 13}`} fill={COLORS.summary} />
        </g>
      );
    }

    const base = t.is_critical ? COLORS.critical : COLORS.normal;
    const done = t.is_critical ? COLORS.criticalDone : COLORS.normalDone;
    const w = g.x2 - g.x1;
    return (
      <g key={k} opacity={dim}>
        <title>{title}</title>
        {baseline}
        <rect
          x={g.x1} y={y + 4} width={w} height={12} rx={1} fill={base} data-bar={k}
          style={canEdit ? { cursor: 'grab' } : undefined}
          onPointerDown={canEdit ? (e) => startBarDrag(e, t, 'move') : undefined}
        />
        {pct > 0 && <rect x={g.x1} y={y + 8} width={w * pct} height={4} fill={done} pointerEvents="none" />}
        {t.constraint_type && <rect x={g.x1} y={y + 4} width={3} height={12} fill="#fbbf24" pointerEvents="none" />}
        {canEdit && (
          <rect
            x={g.x2 - 5} y={y + 4} width={6} height={12} fill="transparent" style={{ cursor: 'ew-resize' }}
            onPointerDown={(e) => startBarDrag(e, t, 'resize')} data-resize={k}
          />
        )}
        {label && !drag && (
          <text x={g.x2 + (canEdit && selected === k ? 16 : 5)} y={y + 15} fontSize="11" fill="#374151" pointerEvents="none">
            {label}
          </text>
        )}
        {handle(g.x2 + 7)}
      </g>
    );
  };

  // ---------------------------------------------------------- table

  const btn = (active) =>
    `px-2.5 py-1 text-xs border ${active ? 'bg-primary text-primary-foreground border-primary' : 'bg-card border-border hover:bg-muted'}`;

  const allCols = useMemo(() => {
    const cols = [
      { key: 'id', label: 'ID', w: 36 },
      { key: 'name', label: 'Task Name', w: 220 },
      { key: 'dur', label: 'Duration', w: editable ? 64 : 74 },
      { key: 'start', label: 'Start', w: editable ? 118 : 96 },
      { key: 'finish', label: 'Finish', w: editable ? 118 : 96 },
      { key: 'pred', label: 'Predecessors', w: editable ? 112 : 90 },
    ];
    cols.push({ key: 'pct', label: '%', w: 48 });
    cols.push({ key: 'res', label: 'Resources', w: 150 });
    return cols;
  }, [editable]);
  const leftCols = useMemo(() => allCols.filter((c) => !hiddenCols.includes(c.key)), [allCols, hiddenCols]);
  const colW = (c) => colWidths[c.key] ?? c.w;
  const leftW = leftCols.reduce((a, c) => a + colW(c), 0);

  // first layout: show the whole table if it fits, otherwise at most 60% of the width
  useLayoutEffect(() => {
    if (paneW === null && bodyRef.current) setPaneW(Math.round(Math.min(leftW, bodyRef.current.clientWidth * 0.6)));
  }, [paneW, leftW]);
  const visibleLeftW = paneW ?? leftW;

  // ---------------------------------------------------------- resizing + independent horizontal scrolling

  const dragResize = (e, onMove) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const move = (ev) => onMove(ev.clientX - startX);
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const startColResize = (e, c) => {
    const startW = colW(c);
    dragResize(e, (dx) => setColWidths((prev) => ({ ...prev, [c.key]: Math.max(32, Math.round(startW + dx)) })));
  };

  const startPaneResize = (e) => {
    const startW = visibleLeftW;
    const total = bodyRef.current ? bodyRef.current.clientWidth : 1000;
    dragResize(e, (dx) => setPaneW(Math.max(160, Math.min(total - 160, Math.round(startW + dx)))));
  };

  // each pane has its own scrollbar; the pane content follows it
  const syncLeft = (e) => { if (leftInnerRef.current) leftInnerRef.current.style.transform = `translateX(${-e.currentTarget.scrollLeft}px)`; };
  const syncRight = (e) => { if (rightInnerRef.current) rightInnerRef.current.style.transform = `translateX(${-e.currentTarget.scrollLeft}px)`; };
  const wheelPane = (barRef) => (e) => {
    const dx = e.shiftKey ? e.deltaY : e.deltaX;
    if (dx && barRef.current) barRef.current.scrollLeft += dx;
  };

  const commitFinish = (t, value) => {
    if (!value || !cal) return;
    const finish = new Date(`${value}T00:00:00`);
    if (t.is_milestone) {
      // a milestone sits at the end of its date: hold it no earlier than the next working day's start
      const b = cal.boundary(finish);
      const next = cal.isWorking(finish) ? cal.dateOf(b + 1) : cal.dateOf(b);
      onEdit(key(t), { constraint_type: 'SNET', constraint_date: ymd(next) });
      return;
    }
    const start = startOfDay(parse(t.start));
    if (finish < start) {
      if (onError) onError('Finish cannot be before the start date.');
      return;
    }
    onEdit(key(t), { duration: { value: Math.max(1, cal.workingDaysBetween(start, finish)), unit: 'D' } });
  };

  const commitPred = (t, text) => {
    const idx = tasks.findIndex((q) => key(q) === key(t));
    const { preds, error } = parsePreds(text, tasks, idx);
    if (error) {
      if (onError) onError(error);
      return;
    }
    onEdit(key(t), { predecessors: preds });
  };

  return (
    <div className="flex flex-col border border-border bg-card" data-testid="program-gantt">
      <div className="flex flex-wrap items-center gap-2 p-2 border-b border-border text-xs">
        <div className="flex">
          {['day', 'week', 'month'].map((z) => (
            <button key={z} className={btn(zoom === z)} onClick={() => setZoomLevel(z)}>
              {z[0].toUpperCase() + z.slice(1)}s
            </button>
          ))}
          <button className={btn(zoom === 'fit')} onClick={fit}>Fit</button>
        </div>
        <div className="flex items-center" role="group" aria-label="Zoom the chart">
          <button className={btn(false)} onClick={() => zoomBy(1 / ZOOM_STEP)} disabled={pxPerDay <= MIN_PX} aria-label="Zoom out" title="Zoom out" data-testid="gantt-zoom-out">&minus;</button>
          <span className="border-y border-border bg-card px-2 py-1 text-xs tabular-nums text-muted-foreground" data-testid="gantt-zoom-level" title="Chart zoom (100% = Days)">{Math.round((pxPerDay / ZOOMS.day) * 100)}%</span>
          <button className={btn(false)} onClick={() => zoomBy(ZOOM_STEP)} disabled={pxPerDay >= MAX_PX} aria-label="Zoom in" title="Zoom in" data-testid="gantt-zoom-in">+</button>
        </div>
        <div className="flex">
          <button className={btn(false)} onClick={expandAll}>Expand all</button>
          <button className={btn(false)} onClick={collapseAll}>Collapse all</button>
        </div>
        <label className="flex items-center gap-1 cursor-pointer">
          <input type="checkbox" checked={showLinks} onChange={(e) => setShowLinks(e.target.checked)} /> Links
        </label>
        <label className="flex items-center gap-1 cursor-pointer">
          <input type="checkbox" checked={showBaseline} onChange={(e) => setShowBaseline(e.target.checked)} /> Baseline
        </label>
        <label className="flex items-center gap-1 cursor-pointer">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> Resource labels
        </label>
        <div className="relative">
          <button className={btn(colMenu)} onClick={() => setColMenu((v) => !v)} aria-expanded={colMenu} data-testid="gantt-columns">Columns{hiddenCols.length ? ` (${allCols.length - hiddenCols.length}/${allCols.length})` : ''}</button>
          {colMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setColMenu(false)} aria-hidden="true" />
              <div className="absolute left-0 top-full z-50 mt-1 w-48 border border-border bg-card p-2 shadow-lg" role="menu" data-testid="gantt-columns-menu">
                {allCols.map((c) => (
                  <label key={c.key} className={`flex items-center gap-2 px-1 py-1 text-xs ${c.key === 'name' ? 'text-muted-foreground' : 'cursor-pointer hover:bg-muted'}`}>
                    <input type="checkbox" disabled={c.key === 'name'} checked={!hiddenCols.includes(c.key)} onChange={() => toggleCol(c.key)} /> {c.label}
                  </label>
                ))}
                {hiddenCols.length > 0 && <button className="mt-1 w-full border-t px-1 pt-2 text-left text-xs underline" onClick={() => { setHiddenCols([]); try { localStorage.removeItem('qsi.gantt.hiddenCols'); } catch { /* ignore */ } }}>Show all columns</button>}
              </div>
            </>
          )}
        </div>
        <div className="ml-auto flex items-center gap-3 text-muted-foreground">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-2" style={{ background: COLORS.normal }} /> Task</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-2" style={{ background: COLORS.critical }} /> Critical</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-2" style={{ background: COLORS.summary }} /> Summary</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-1" style={{ background: COLORS.baseline }} /> Baseline</span>
        </div>
      </div>

      <div ref={bodyRef} className="overflow-y-auto overflow-x-hidden relative" style={{ maxHeight: editable ? 'calc(100vh - 21rem)' : 'calc(100vh - 14.5rem)', minHeight: 320 }}>
        <div className="flex items-stretch">
          {/* Table pane */}
          <div className="flex-none" style={{ width: visibleLeftW, overflowX: 'clip' }} onWheel={wheelPane(leftBarRef)}>
            <div ref={leftInnerRef} style={{ width: leftW, willChange: 'transform' }}>
            <div className="flex bg-muted border-b border-r border-border text-[11px] font-semibold sticky top-0 z-30" style={{ width: leftW, height: HEAD_H }}>
              {leftCols.map((c) => (
                <div key={c.key} className="relative px-1.5 flex items-end pb-1 border-r border-border/60" style={{ width: colW(c), paddingLeft: c.key === 'name' ? 6 + NAME_GUTTER : undefined }}>
                  <span className="truncate">{c.label}</span>
                  <span
                    className="absolute right-0 top-0 h-full w-2 -mr-1 z-10 cursor-col-resize hover:bg-primary/50"
                    title="Drag to resize (double-click to reset)"
                    data-col-resize={c.key}
                    onPointerDown={(e) => startColResize(e, c)}
                    onDoubleClick={() => setColWidths((prev) => { const n = { ...prev }; delete n[c.key]; return n; })}
                  />
                </div>
              ))}
            </div>
            <div className="bg-card border-r border-border" style={{ width: leftW, height: bodyH }}>
              {rows.length === 0 && (
                <div className="p-4 text-xs text-muted-foreground whitespace-normal">No tasks yet. Use "Add task" in the toolbar to start building the programme.</div>
              )}
              {rows.map((t) => {
                const k = key(t);
                const sel = selectedSet.has(k);
                const leaf = !t.is_summary;
                return (
                  <div
                    key={k}
                    data-row={k}
                    onClick={(e) => {
                      if (e.shiftKey && selected != null && rowIndex.has(selected)) {
                        const a = rowIndex.get(selected);
                        const b = rowIndex.get(k);
                        select(k, { mode: 'range', uids: rows.slice(Math.min(a, b), Math.max(a, b) + 1).map(key) });
                      } else if (e.ctrlKey || e.metaKey) select(k, { mode: 'toggle' });
                      else select(k);
                    }}
                    className={`flex text-xs border-b border-border/40 cursor-default ${sel ? 'bg-primary/15' : 'hover:bg-muted/50'} ${t.is_summary ? 'font-bold' : ''}`}
                    style={{ height: ROW_H, lineHeight: `${ROW_H - 1}px`, opacity: t.is_active === false ? 0.5 : 1 }}
                  >
                    {leftCols.map((c) => (
                      <div key={c.key} className="px-1.5 border-r border-border/40 whitespace-nowrap overflow-hidden text-ellipsis flex items-center" style={{ width: colW(c) }}>
                        {c.key === 'id' && t.id}
                        {c.key === 'name' && (
                          <span className="flex items-center w-full min-w-0" style={{ paddingLeft: (t.outline_level - 1) * 12 }} title={t.name}>
                            <span className="flex-none flex items-center justify-start" style={{ width: NAME_GUTTER }}>
                              {t.is_summary && (
                                <button onClick={(e) => { e.stopPropagation(); toggle(k); }} className="text-muted-foreground">
                                  {collapsed.has(k) ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                </button>
                              )}
                            </span>
                            {editable ? (
                              <CellInput
                                value={t.name}
                                dataAttr={{ 'data-name-uid': k }}
                                className={t.is_summary ? 'font-bold' : ''}
                                onCommit={(v) => onEdit(k, { name: v.trim() || 'Untitled' })}
                              />
                            ) : (
                              <span className="truncate">{t.name}</span>
                            )}
                          </span>
                        )}
                        {c.key === 'dur' && (editable && leaf ? (
                          <CellInput
                            type="number" min="0" step="1" dataAttr={{ 'data-dur-uid': k }}
                            value={t.is_milestone ? 0 : t.duration?.value}
                            onCommit={(v) => { const n = Math.max(0, Math.round(Number(v))); if (!Number.isNaN(n)) onEdit(k, { duration: { value: n, unit: 'D' } }); }}
                          />
                        ) : fmtDuration(t.duration, t.is_milestone))}
                        {c.key === 'start' && (editable && leaf && !t.is_milestone ? (
                          <span className="flex items-center w-full">
                            <CellInput
                              type="date" value={(t.start || '').slice(0, 10)} dataAttr={{ 'data-start-uid': k }}
                              onCommit={(v) => v && onEdit(k, { constraint_type: t.constraint_type === 'MSO' ? 'MSO' : 'SNET', constraint_date: v })}
                            />
                            {t.constraint_type && (
                              <button
                                className="ml-0.5 text-amber-500 hover:text-amber-600 flex-none"
                                title={`${CONSTRAINT_LABEL[t.constraint_type]} ${t.constraint_date}. Click to release (let links decide).`}
                                onClick={(e) => { e.stopPropagation(); onEdit(k, { constraint_type: null, constraint_date: null }); }}
                              >
                                <Pin className="w-3 h-3" />
                              </button>
                            )}
                          </span>
                        ) : fmtDate(t.start))}
                        {c.key === 'finish' && (editable && leaf ? (
                          <CellInput
                            type="date" value={(t.finish || '').slice(0, 10)} dataAttr={{ 'data-finish-uid': k }}
                            onCommit={(v) => commitFinish(t, v)}
                          />
                        ) : fmtDate(t.finish))}
                        {c.key === 'pred' && (editable ? (
                          <span className="flex items-center w-full min-w-0 gap-1">
                            <CellInput value={formatPreds(t)} dataAttr={{ 'data-pred-uid': k }} onCommit={(v) => commitPred(t, v)} placeholder="e.g. 5, 7SS+2d" />
                            {onOpenLinks && (
                              <button
                                className="flex-none text-muted-foreground hover:text-primary" title="Edit dependencies"
                                data-links-uid={k} onClick={(e) => { e.stopPropagation(); select(k); onOpenLinks(k); }}
                              >
                                <Link2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </span>
                        ) : formatPreds(t))}
                        {c.key === 'pct' && (editable && leaf ? (
                          <CellInput
                            type="number" min="0" max="100" value={Math.round(t.percent_complete || 0)}
                            onCommit={(v) => { const n = Math.max(0, Math.min(100, Math.round(Number(v)))); if (!Number.isNaN(n)) onEdit(k, { percent_complete: n }); }}
                          />
                        ) : `${Math.round(t.percent_complete || 0)}%`)}
                        {c.key === 'res' && (
                          <button
                            className={`flex items-center gap-1 w-full text-left ${leaf && editable ? 'hover:text-primary' : 'cursor-default'}`}
                            disabled={!leaf || !editable}
                            data-res-uid={k}
                            onClick={(e) => { e.stopPropagation(); select(k); if (onOpenResources) onOpenResources(k); }}
                            title={leaf && editable ? 'Assign resources' : ''}
                          >
                            {leaf && editable && <Users className="w-3 h-3 flex-none text-muted-foreground" />}
                            <span className="truncate">{assignmentNames(t).join(', ')}</span>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
            </div>
          </div>

          {/* Draggable divider between the table and the timeline */}
          <div
            className="flex-none w-1.5 cursor-col-resize bg-border hover:bg-primary/60 active:bg-primary z-40"
            title="Drag to resize the table and timeline"
            data-testid="gantt-divider"
            onPointerDown={startPaneResize}
          />

          {/* Timeline pane */}
          <div className="flex-1 min-w-0" style={{ overflowX: 'clip' }} onWheel={wheelPane(rightBarRef)}>
            <div ref={rightInnerRef} style={{ width: totalW, willChange: 'transform' }}>
            <div className="relative bg-muted border-b border-border text-[11px] sticky top-0 z-30" style={{ width: totalW, height: HEAD_H }}>
              {header.top.map((h, i) => (
                <div key={i} className="absolute top-0 border-r border-b border-border/60 px-1 truncate" style={{ left: h.left, width: h.width, height: HEAD_H / 2 }}>
                  {h.label}
                </div>
              ))}
              {header.bottom.map((h, i) => (
                <div key={i} className="absolute border-r border-border/40 text-center truncate text-muted-foreground" style={{ left: h.left, width: h.width, top: HEAD_H / 2, height: HEAD_H / 2, lineHeight: `${HEAD_H / 2}px` }}>
                  {pxPerDay >= 5 ? h.label : ''}
                </div>
              ))}
            </div>
            <svg ref={svgRef} width={totalW} height={bodyH} className="block" style={{ flex: 'none', touchAction: 'none' }}>
              <defs>
                <marker id="pg-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L6,3 L0,6 z" fill={COLORS.link} />
                </marker>
              </defs>
              {shading.map((k) => (
                <rect key={k} x={k * pxPerDay} y={0} width={pxPerDay} height={bodyH} fill="#9CA3AF" opacity={0.14} />
              ))}
              {pxPerDay >= 18 && header.bottom.map((h, i) => <line key={i} x1={h.left} x2={h.left} y1={0} y2={bodyH} stroke="#9CA3AF" strokeOpacity={0.15} />)}
              {rows.map((t, i) => (
                <g key={key(t)}>
                  {selectedSet.has(key(t)) && <rect x={0} y={i * ROW_H} width={totalW} height={ROW_H} fill="#3b82f6" opacity={0.1} />}
                  {linking && Math.floor(linking.y / ROW_H) === i && key(t) !== linking.fromUid && (
                    <rect x={0} y={i * ROW_H} width={totalW} height={ROW_H} fill="#22c55e" opacity={0.2} />
                  )}
                  <line x1={0} x2={totalW} y1={(i + 1) * ROW_H} y2={(i + 1) * ROW_H} stroke="#9CA3AF" strokeOpacity={0.2} />
                </g>
              ))}
              {showToday && <line x1={todayX} x2={todayX} y1={0} y2={bodyH} stroke="#16a34a" strokeWidth={1.5} strokeDasharray="4 3" />}
              {statusX !== null && <line x1={statusX} x2={statusX} y1={0} y2={bodyH} stroke="#7c3aed" strokeWidth={1} />}
              {rows.map(renderBar)}
              {links.map((l) => (
                <path key={l.key} d={l.d} fill="none" stroke={l.hot ? '#2563eb' : COLORS.link} strokeWidth={l.hot ? 1.6 : 1} markerEnd="url(#pg-arrow)" pointerEvents="none" />
              ))}
              {linking && (() => {
                const fi = rowIndex.get(linking.fromUid);
                const ft = tasks.find((q) => key(q) === linking.fromUid);
                const fg = ft && geom(ft);
                if (fi === undefined || !fg) return null;
                return <line x1={fg.x2} y1={fi * ROW_H + ROW_H / 2} x2={linking.x} y2={linking.y} stroke="#2563eb" strokeWidth={1.5} strokeDasharray="4 3" pointerEvents="none" />;
              })()}
              {drag && (() => {
                const t = tasks.find((q) => key(q) === drag.uid);
                const g = t && geom(t);
                if (!g) return null;
                const days = Math.round(drag.dx / pxPerDay);
                const base = drag.mode === 'move' ? parse(t.start) : parse(t.finish);
                const d = addDays(base, days);
                return (
                  <text x={g.x2 + 8} y={(rowIndex.get(drag.uid) ?? 0) * ROW_H + 16} fontSize="11" fill="#2563eb" fontWeight="600" pointerEvents="none">
                    {drag.mode === 'move' ? 'Start ' : 'Finish '}{fmtDate(ymd(d))}
                  </text>
                );
              })()}
            </svg>
            </div>
          </div>
        </div>
      </div>

      {/* One horizontal scrollbar per pane, so each side moves independently */}
      <div className="flex border-t border-border bg-muted/40">
        <div ref={leftBarRef} className="flex-none overflow-x-auto overflow-y-hidden" style={{ width: visibleLeftW, minHeight: 14, scrollbarWidth: 'auto' }} onScroll={syncLeft} data-testid="gantt-scroll-table">
          <div style={{ width: leftW, height: 1 }} />
        </div>
        <div className="flex-none w-1.5" />
        <div ref={rightBarRef} className="flex-1 min-w-0 overflow-x-auto overflow-y-hidden" style={{ minHeight: 14, scrollbarWidth: 'auto' }} onScroll={syncRight} data-testid="gantt-scroll-timeline">
          <div style={{ width: totalW, height: 1 }} />
        </div>
      </div>
    </div>
  );
};

export default ProgramGantt;
