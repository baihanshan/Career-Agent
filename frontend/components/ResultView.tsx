import type { AnalysisResult } from "../lib/types";
import { ProcessingWarnings } from "./ProcessingWarnings";
import { RiskWarnings } from "./RiskWarnings";

interface ResultViewProps {
  result: AnalysisResult;
}

const riskLevelLabels = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
} as const;

export function ResultView({ result }: ResultViewProps) {
  const assets = result.generated_assets;

  return (
    <div className="results-grid">
      <div className="result-main">
        <section className="panel">
          <h2>匹配总结</h2>
          <p>{assets.match_summary}</p>
        </section>

        <section className="panel">
          <h2>简历要点</h2>
          <div className="bullet-list">
            {assets.resume_bullets.map((bullet) => (
              <article className="bullet-item" key={`${bullet.text}-${bullet.risk_level}`}>
                <p>{bullet.text}</p>
                <div className="chip-row">
                  {bullet.evidence_ids.map((id) => (
                    <span className="chip" key={id}>
                      证据来源：{id}
                    </span>
                  ))}
                  <span className={`chip risk-${bullet.risk_level}`}>
                    风险：{riskLevelLabels[bullet.risk_level]}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>面试准备</h2>
          <div className="prep-list">
            {assets.interview_prep.map((item) => (
              <article className="prep-item" key={item.topic}>
                <h3>{item.topic}</h3>
                <p>{item.why_it_matters}</p>
                <strong>{item.prep_suggestion}</strong>
              </article>
            ))}
          </div>
        </section>
      </div>

      <aside className="result-side">
        <ProcessingWarnings warnings={result.processing_warnings ?? []} />
        <RiskWarnings report={result.evaluation_report} />
      </aside>
    </div>
  );
}
