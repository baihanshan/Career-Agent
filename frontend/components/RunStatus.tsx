interface RunStatusProps {
  status: "idle" | "loading" | "success" | "error";
  errorMessage?: string;
}

const statusText = {
  idle: "等待输入",
  loading: "正在分析",
  success: "分析完成",
  error: "分析失败",
};

export function RunStatus({ status, errorMessage }: RunStatusProps) {
  return (
    <section className={`status status-${status}`} aria-live="polite">
      <div>
        <span className="eyebrow">运行状态</span>
        <strong>{statusText[status]}</strong>
      </div>
      {status === "loading" ? <div className="progress-bar" /> : null}
      {errorMessage ? <p>{errorMessage}</p> : null}
    </section>
  );
}
