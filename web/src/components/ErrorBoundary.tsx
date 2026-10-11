import { Component, type ReactNode } from "react";

/** Catches a crash inside one page so the estimator sees a readable message (and the menu still works) instead of a blank screen. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error("Page crashed:", error); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="border border-red-line bg-red-bg px-4 py-4 text-sm text-red-fg">
        <div className="font-heading text-sm font-bold uppercase">This page hit a problem</div>
        <p className="mt-2">Nothing has been lost or changed. Try another page from the menu, or reload. If it keeps happening, send Rick's developer this message:</p>
        <p className="mt-2 break-all font-mono text-xs">{this.state.error.message}</p>
        <button className="btn btn-ghost mt-3" onClick={() => window.location.reload()}>Reload</button>
      </div>
    );
  }
}
