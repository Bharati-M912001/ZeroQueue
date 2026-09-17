// The Moss Trace strip: proof of what the retrieval layer did for the
// latest answer. This is what judges look at for the latency criterion.
export type Trace = {
  state: string;
  retrieval_ms?: number | null;
  total_ms?: number | null;
  source_count: number;
  sources: { label: string; url?: string | null }[];
  confidence_band?: string | null;
  handoff_reason?: string | null;
};

export default function TraceCard({ trace }: { trace: Trace | null }) {
  if (!trace || trace.state === "empty") {
    return (
      <div className="trace">
        <h2>Moss Trace</h2>
        Ask a question and this shows the retrieval time, total time, and the
        exact sources the answer used.
      </div>
    );
  }
  return (
    <div className="trace">
      <h2>Moss Trace - {trace.state}</h2>
      <div className="nums">
        <div><b>{trace.retrieval_ms ?? "-"} ms</b>retrieval</div>
        <div><b>{trace.total_ms ?? "-"} ms</b>total</div>
        <div><b>{trace.source_count}</b>sources</div>
        <div><b>{trace.confidence_band ?? "-"}</b>confidence</div>
      </div>
      {trace.handoff_reason ? (
        <div className="reason">Handoff reason: {trace.handoff_reason}</div>
      ) : null}
      {trace.sources.length > 0 && (
        <ul>
          {trace.sources.map((s) => <li key={s.label}>{s.label}</li>)}
        </ul>
      )}
    </div>
  );
}
