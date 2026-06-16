import type { EvaluationReport } from "../lib/types";

interface RiskWarningsProps {
  report: EvaluationReport;
}

export function RiskWarnings({ report }: RiskWarningsProps) {
  return (
    <section className="panel risk-panel">
      <h2>风险提示</h2>
      <p className="risk-summary">{report.risk_summary}</p>
      <div className="warning-list">
        {report.grounding_warnings.map((warning) => (
          <article className="warning-item" key={`${warning.asset_id}-${warning.claim}`}>
            <span className={`severity severity-${warning.severity}`}>
              严重程度：{warning.severity}
            </span>
            <strong>{warning.claim}</strong>
            <p>{warning.reason}</p>
          </article>
        ))}
        {report.coverage_gaps.map((gap) => (
          <article className="warning-item" key={gap.requirement_id}>
            <span className={`severity severity-${gap.severity}`}>
              严重程度：{gap.severity}
            </span>
            <strong>未覆盖要求：{gap.requirement_id}</strong>
            <p>{gap.reason}</p>
          </article>
        ))}
      </div>
      {report.specificity_notes.length > 0 ? (
        <ul className="specificity-list">
          {report.specificity_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
