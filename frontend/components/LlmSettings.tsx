import { useMemo, useState } from "react";

import { listModels } from "../lib/api";
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
  const canListModels =
    value.provider !== "local" &&
    value.apiKey.trim().length > 0 &&
    (value.provider !== "openai_compatible" || value.baseUrl.trim().length > 0);
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelListMessage, setModelListMessage] = useState("");
  const datalistId = useMemo(
    () => `model-options-${value.provider}`,
    [value.provider]
  );

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
    setModelOptions([]);
    setModelListMessage("");
  }

  async function handleListModels() {
    if (!canListModels || isLoadingModels) {
      return;
    }

    setIsLoadingModels(true);
    setModelListMessage("");
    try {
      const response = await listModels({
        provider: value.provider,
        api_key: value.apiKey.trim(),
        base_url:
          value.provider === "deepseek" || value.provider === "openai_compatible"
            ? value.baseUrl.trim()
            : undefined,
      });
      const options = response.models.map((model) => model.id);
      setModelOptions(options);
      setModelListMessage(
        response.warning ??
          (options.length > 0 ? `已获取 ${options.length} 个模型。` : "未获取到模型列表，请手动输入。")
      );
    } catch {
      setModelOptions([]);
      setModelListMessage("模型列表获取失败，请手动输入模型名。");
    } finally {
      setIsLoadingModels(false);
    }
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
          list={modelOptions.length > 0 ? datalistId : undefined}
          value={value.model}
          onChange={(event) => update({ model: event.target.value })}
          placeholder="deepseek-v4-flash"
        />
        <datalist id={datalistId}>
          {modelOptions.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
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

      <div className="model-list-actions">
        <button
          type="button"
          disabled={!canListModels || isLoadingModels}
          onClick={handleListModels}
        >
          {isLoadingModels ? "获取中..." : "获取模型列表"}
        </button>
        <span>{modelListMessage || "模型可下拉选择，也可以手动输入。"}</span>
      </div>
    </section>
  );
}
