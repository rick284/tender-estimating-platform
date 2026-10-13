import { useReducer, useMemo, useCallback } from 'react';
import {
  calendarFor, ensureUids, renumber, schedule, normalizeImported,
  insertTask, deleteTask, indentTask, outdentTask, moveTask, ymd,
} from './programSchedule';

/**
 * Editing state for a programme: tasks (always scheduled), selection, undo/redo, dirty flag.
 * All changes go through commit(), which renumbers, reschedules and rejects circular links.
 */

const HISTORY = 60;

function init(doc) {
  const meta = {
    name: doc.name,
    start: doc.start,
    working_days: doc.working_days || [true, true, true, true, true, false, false],
    non_working_dates: doc.non_working_dates || [],
  };
  const cal = calendarFor(meta, doc.tasks);
  let tasks = doc.tasks || [];
  if (tasks.length) {
    if (doc.needs_schedule || doc.normalized) {
      const res = schedule(renumber(ensureUids(tasks)), cal);
      tasks = res.error ? renumber(ensureUids(tasks)) : res.tasks;
    } else {
      tasks = normalizeImported(tasks, cal).tasks;
    }
  }
  return { ...meta, tasks, past: [], future: [], dirty: !!doc.needs_schedule, selectedUid: null, selectedUids: [], error: null, errorId: 0 };
}

function commit(state, rawTasks, extra = {}) {
  const meta = { ...state, ...extra };
  const cal = calendarFor(meta, rawTasks);
  const res = schedule(renumber(rawTasks), cal);
  if (res.error) {
    return { ...state, error: 'That link would create a loop (a task cannot depend on itself, directly or indirectly).', errorId: state.errorId + 1 };
  }
  return {
    ...state,
    ...extra,
    tasks: res.tasks,
    past: [...state.past, { tasks: state.tasks, start: state.start }].slice(-HISTORY),
    future: [],
    dirty: true,
    error: null,
  };
}

function reducer(state, a) {
  switch (a.type) {
    case 'LOAD':
      return init(a.doc);
    case 'SELECT': {
      if (a.uid == null) return { ...state, selectedUid: null, selectedUids: [] };
      if (a.mode === 'range' && a.uids) return { ...state, selectedUid: a.uid, selectedUids: a.uids };
      if (a.mode === 'toggle') {
        const has = state.selectedUids.includes(a.uid);
        const next = has ? state.selectedUids.filter((u) => u !== a.uid) : [...state.selectedUids, a.uid];
        return { ...state, selectedUid: has ? next[next.length - 1] ?? null : a.uid, selectedUids: next };
      }
      return { ...state, selectedUid: a.uid, selectedUids: [a.uid] };
    }
    case 'SAVED':
      return { ...state, dirty: false };
    case 'EDIT': {
      const tasks = state.tasks.map((t) => (t.uid === a.uid ? { ...t, ...a.patch } : t));
      return commit(state, tasks);
    }
    case 'LINK': {
      const to = state.tasks.find((t) => t.uid === a.to);
      if (!to || a.from === a.to) return state;
      if ((to.predecessors || []).some((p) => p.uid === a.from)) return state;
      const tasks = state.tasks.map((t) => (t.uid === a.to ? { ...t, predecessors: [...(t.predecessors || []), { uid: a.from, type: 'FS', lag_days: 0 }] } : t));
      return commit(state, tasks);
    }
    case 'INSERT': {
      const idx = a.afterUid != null ? state.tasks.findIndex((t) => t.uid === a.afterUid) : state.tasks.length - 1;
      const res = insertTask(state.tasks, idx, a.props || {});
      const next = commit(state, res.tasks);
      return next.error ? next : { ...next, selectedUid: res.tasks[res.index].uid, selectedUids: [res.tasks[res.index].uid] };
    }
    case 'DELETE': {
      let tasks = state.tasks;
      (a.uids || [a.uid]).forEach((uid) => {
        const idx = tasks.findIndex((t) => t.uid === uid);
        if (idx >= 0) tasks = deleteTask(tasks, idx);
      });
      if (tasks === state.tasks) return state;
      const next = commit(state, tasks);
      return { ...next, selectedUid: null, selectedUids: [] };
    }
    case 'LINK_SELECTED': {
      const sel = new Set(state.selectedUids);
      const ordered = state.tasks.filter((t) => sel.has(t.uid));
      if (ordered.length < 2) return state;
      const tasks = state.tasks.map((t) => {
        const i = ordered.findIndex((o) => o.uid === t.uid);
        if (i <= 0) return t;
        const prev = ordered[i - 1].uid;
        if ((t.predecessors || []).some((p) => p.uid === prev)) return t;
        return { ...t, predecessors: [...(t.predecessors || []), { uid: prev, type: 'FS', lag_days: 0 }] };
      });
      return commit(state, tasks);
    }
    case 'UNLINK_SELECTED': {
      const sel = new Set(state.selectedUids);
      if (!sel.size) return state;
      const single = sel.size === 1;
      const tasks = state.tasks.map((t) => {
        const preds = t.predecessors || [];
        const keep = preds.filter((p) => {
          if (single) return !(sel.has(t.uid) || sel.has(p.uid)); // all links to/from the one task
          return !(sel.has(t.uid) && sel.has(p.uid)); // links among the selected tasks
        });
        return keep.length === preds.length ? t : { ...t, predecessors: keep };
      });
      return commit(state, tasks);
    }
    case 'INDENT': {
      const idx = state.tasks.findIndex((t) => t.uid === a.uid);
      return idx < 0 ? state : commit(state, indentTask(state.tasks, idx));
    }
    case 'OUTDENT': {
      const idx = state.tasks.findIndex((t) => t.uid === a.uid);
      return idx < 0 ? state : commit(state, outdentTask(state.tasks, idx));
    }
    case 'MOVE': {
      const idx = state.tasks.findIndex((t) => t.uid === a.uid);
      return idx < 0 ? state : commit(state, moveTask(state.tasks, idx, a.dir).tasks);
    }
    case 'SET_START':
      return commit(state, state.tasks, { start: `${a.date}T08:00` });
    case 'SET_NAME':
      return { ...state, name: a.name, dirty: true };
    case 'UNDO': {
      if (!state.past.length) return state;
      const prev = state.past[state.past.length - 1];
      return {
        ...state,
        tasks: prev.tasks,
        start: prev.start,
        past: state.past.slice(0, -1),
        future: [{ tasks: state.tasks, start: state.start }, ...state.future],
        dirty: true,
        error: null,
      };
    }
    case 'REDO': {
      if (!state.future.length) return state;
      const nxt = state.future[0];
      return {
        ...state,
        tasks: nxt.tasks,
        start: nxt.start,
        future: state.future.slice(1),
        past: [...state.past, { tasks: state.tasks, start: state.start }],
        dirty: true,
        error: null,
      };
    }
    default:
      return state;
  }
}

export default function useProgramEditor(doc) {
  const [state, dispatch] = useReducer(reducer, doc, init);

  const cal = useMemo(
    () => calendarFor({ start: state.start, working_days: state.working_days, non_working_dates: state.non_working_dates }, state.tasks),
    [state.start, state.working_days, state.non_working_dates, state.tasks]
  );

  const d = useCallback((action) => dispatch(action), []);
  const actions = useMemo(
    () => ({
      select: (uid, opts = {}) => d({ type: 'SELECT', uid, ...opts }),
      edit: (uid, patch) => d({ type: 'EDIT', uid, patch }),
      link: (from, to) => d({ type: 'LINK', from, to }),
      insert: (afterUid, props) => d({ type: 'INSERT', afterUid, props }),
      remove: (uid) => d({ type: 'DELETE', uid }),
      removeMany: (uids) => d({ type: 'DELETE', uids }),
      linkSelected: () => d({ type: 'LINK_SELECTED' }),
      unlinkSelected: () => d({ type: 'UNLINK_SELECTED' }),
      indent: (uid) => d({ type: 'INDENT', uid }),
      outdent: (uid) => d({ type: 'OUTDENT', uid }),
      move: (uid, dir) => d({ type: 'MOVE', uid, dir }),
      setStart: (date) => d({ type: 'SET_START', date }),
      setName: (name) => d({ type: 'SET_NAME', name }),
      undo: () => d({ type: 'UNDO' }),
      redo: () => d({ type: 'REDO' }),
      saved: () => d({ type: 'SAVED' }),
      load: (nextDoc) => d({ type: 'LOAD', doc: nextDoc }),
    }),
    [d]
  );

  return {
    tasks: state.tasks,
    cal,
    name: state.name,
    start: state.start,
    working_days: state.working_days,
    non_working_dates: state.non_working_dates,
    selectedUid: state.selectedUid,
    selectedUids: state.selectedUids,
    dirty: state.dirty,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    error: state.error,
    errorId: state.errorId,
    projectStartYmd: state.start ? state.start.slice(0, 10) : ymd(new Date()),
    actions,
  };
}
