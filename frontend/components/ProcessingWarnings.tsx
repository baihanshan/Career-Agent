import type { ProcessingWarning } from "../lib/types";

interface ProcessingWarningsProps {
  warnings: ProcessingWarning[];
}

export function ProcessingWarnings({ warnings }: ProcessingWarningsProps) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <section className="panel warning-panel">
      <h2>流程警告</h2>
      <div className="warning-list">
        {warnings.map((warning) => (
          <article className="warning-item" key={`${warning.code}-${warning.source ?? "global"}`}>
            <span className="severity severity-medium">{warning.code}</span>
            <strong>{warning.source ?? "全局提示"}</strong>
            <p>{warning.message}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
