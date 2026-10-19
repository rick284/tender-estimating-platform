import { Fragment, type ReactNode } from "react";

// A small, safe Markdown reader for the step briefs and reports: headings, lists, tables, code blocks, bold, code. Nothing is interpreted as HTML.
function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const t = m[0];
    out.push(t.startsWith("**") ? <strong key={i++}>{t.slice(2, -2)}</strong> : <code key={i++} className="bg-muted px-1 font-mono text-[0.85em]">{t.slice(1, -1)}</code>);
    last = m.index + t.length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
const cells = (l: string) => l.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.trim().startsWith("```")) {
      const code: string[] = []; i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push(<pre key={k++} className="my-3 overflow-x-auto border bg-muted p-3 text-xs">{code.join("\n")}</pre>);
    } else if (/^#{1,6}\s/.test(l)) {
      const n = l.match(/^#+/)![0].length;
      const t = l.replace(/^#+\s*/, "");
      blocks.push(n <= 1 ? <h2 key={k++} className="mb-2 mt-5 text-lg font-semibold normal-case">{inline(t)}</h2> : <h3 key={k++} className="mb-1 mt-4 text-sm font-semibold normal-case">{inline(t)}</h3>);
      i++;
    } else if (l.trim().startsWith("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      const head = cells(l); i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      blocks.push(
        <div key={k++} className="my-3 overflow-x-auto"><table className="grid-table"><thead><tr>{head.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead>
          <tbody>{rows.map((r, a) => <tr key={a}>{head.map((_, j) => <td key={j}>{inline(r[j] ?? "")}</td>)}</tr>)}</tbody></table></div>,
      );
    } else if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const items: string[] = [];
      const ordered = /^\s*\d+\./.test(l);
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const L = ordered ? "ol" : "ul";
      blocks.push(<L key={k++} className={`my-2 ml-5 space-y-0.5 text-sm ${ordered ? "list-decimal" : "list-disc"}`}>{items.map((t, a) => <li key={a}>{inline(t)}</li>)}</L>);
    } else if (l.trim() === "") {
      i++;
    } else {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,6}\s|```|\s*([-*]|\d+\.)\s|\|)/.test(lines[i])) para.push(lines[i++]);
      if (!para.length) { para.push(lines[i++]); }
      blocks.push(<p key={k++} className="my-2 text-sm leading-snug">{para.map((t, a) => <Fragment key={a}>{a > 0 && <br />}{inline(t)}</Fragment>)}</p>);
    }
  }
  return <div>{blocks}</div>;
}
