interface JobDescriptionInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function JobDescriptionInput({ value, onChange }: JobDescriptionInputProps) {
  return (
    <label className="field">
      <span>目标岗位 JD</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="粘贴目标岗位描述、职责、技能要求和加分项"
        rows={12}
      />
    </label>
  );
}
