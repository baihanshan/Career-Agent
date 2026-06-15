import type { EvidenceItem } from "../lib/types";

interface EvidenceTableProps {
  evidence: EvidenceItem[];
}

export function EvidenceTable({ evidence }: EvidenceTableProps) {
  return (
    <section className="panel">
      <h2>证据表</h2>
      {evidence.length === 0 ? (
        <p className="muted">暂无可展示证据。</p>
      ) : (
        <div className="evidence-list">
          {evidence.map((item) => (
            <article className="evidence-item" key={item.evidence_id}>
              <div className="evidence-meta">
                <span>{item.source_name}</span>
                {item.section_label ? <span>{item.section_label}</span> : null}
                <span>score {item.score.toFixed(2)}</span>
              </div>
              <p>{item.snippet}</p>
              <code>{item.evidence_id}</code>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
