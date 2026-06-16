import type { LlmProvider } from "../lib/types";

export interface LlmSettingsValue {
  provider: LlmProvider;
  apiKey: string;
  model: string;
  baseUrl: string;
  temperature: number;
}

interface LlmSettingsProps {
  value: LlmSettingsValue;
  onChange: (value: LlmSettingsValue) => void;
}

const PROVIDER_DEFAULTS: Record<
  LlmProvider,
  Pick<LlmSettingsValue, "model" | "baseUrl">
> = {
  local: {
    model: "default",
    baseUrl: "",
  },
  openai: {
    model: "gpt-4.1",
    baseUrl: "",
  },
  deepseek: {
    model: "deepseek-v4-flash",
    baseUrl: "https://api.deepseek.com",
  },
  openai_compatible: {
    model: "",
    baseUrl: "",
  },
};

export function LlmSettings({ value, onChange }: LlmSettingsProps) {
  const requiresApiKey = value.provider !== "local";

  function update(patch: Partial<LlmSettingsValue>) {
    onChange({ ...value, ...patch });
  }

  function handleProviderChange(provider: LlmProvider) {
    const defaults = PROVIDER_DEFAULTS[provider];
    onChange({
      ...value,
      provider,
      apiKey: provider === "local" ? "" : value.apiKey,
      model: defaults.model,
      baseUrl: defaults.baseUrl,
    });
  }

  return (
    <section className="llm-settings">
      <label className="field compact-field">
        <span>模型服务</span>
        <select
          value={value.provider}
          onChange={(event) => handleProviderChange(event.target.value as LlmProvider)}
        >
          <option value="deepseek">DeepSeek</option>
          <option value="openai">OpenAI</option>
          <option value="openai_compatible">兼容接口</option>
          <option value="local">本地演示</option>
        </select>
      </label>

      <label className="field compact-field">
        <span>API Key</span>
        <input
          type="password"
          value={value.apiKey}
          disabled={!requiresApiKey}
          onChange={(event) => update({ apiKey: event.target.value })}
          placeholder={requiresApiKey ? "sk-..." : "本地演示无需填写"}
          autoComplete="off"
        />
      </label>

      <label className="field compact-field">
        <span>模型</span>
        <input
          value={value.model}
          onChange={(event) => update({ model: event.target.value })}
          placeholder="deepseek-v4-flash"
        />
      </label>

      <label className="field compact-field">
        <span>Base URL</span>
        <input
          value={value.baseUrl}
          disabled={value.provider === "openai" || value.provider === "local"}
          onChange={(event) => update({ baseUrl: event.target.value })}
          placeholder="https://api.deepseek.com"
        />
      </label>

      <label className="field compact-field">
        <span>Temperature</span>
        <input
          type="number"
          min="0"
          max="2"
          step="0.1"
          value={value.temperature}
          onChange={(event) => update({ temperature: Number(event.target.value) })}
        />
      </label>
    </section>
  );
}
