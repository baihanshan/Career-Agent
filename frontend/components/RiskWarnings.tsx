import type { EvaluationReport, RiskReport } from "../lib/types";

interface RiskWarningsProps {
  report: EvaluationReport;
  riskReport?: RiskReport | null;
}

const severityLabels = {
  low: "低严重程度",
  medium: "中严重程度",
  high: "高严重程度",
} as const;

export function RiskWarnings({ report, riskReport }: RiskWarningsProps) {
  if (riskReport) {
    return (
      <section className="panel risk-panel">
        <h2>风险提示</h2>
        <div className="warning-list">
          {riskReport.risks.slice(0, 3).map((risk) => (
            <article
              className="warning-item"
              key={`${risk.risk_type}-${risk.title}-${risk.jd_requirement_summary}`}
            >
              <span className={`severity severity-${risk.severity}`}>
                严重程度：{severityLabels[risk.severity]}
              </span>
              <strong>{risk.title}</strong>
              <p>对应 JD 要求：{risk.jd_requirement_summary}</p>
              <p>简历现状：{risk.resume_current_state}</p>
              <p>风险原因：{risk.risk_reason}</p>
              <p>建议：{risk.recommendation}</p>
            </article>
          ))}
          {riskReport.risks.length === 0 ? <p>暂未发现需要优先处理的风险。</p> : null}
        </div>
      </section>
    );
  }

  return (
    <section className="panel risk-panel">
      <h2>风险提示</h2>
      <p className="risk-summary">{report.risk_summary}</p>
      <div className="warning-list">
        {report.grounding_warnings.map((warning) => (
          <article className="warning-item" key={`${warning.asset_id}-${warning.claim}`}>
            <span className={`severity severity-${warning.severity}`}>
              严重程度：{severityLabels[warning.severity]}
            </span>
            <strong>{warning.claim}</strong>
            <p>{warning.reason}</p>
          </article>
        ))}
        {report.coverage_gaps.map((gap) => (
          <article className="warning-item" key={gap.requirement_id}>
            <span className={`severity severity-${gap.severity}`}>
              严重程度：{severityLabels[gap.severity]}
            </span>
            <strong>未覆盖要求：{gap.requirement_text ?? gap.reason}</strong>
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
