interface ProfileInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function ProfileInput({ value, onChange }: ProfileInputProps) {
  return (
    <label className="field">
      <span>个人材料</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="粘贴简历、项目经历、课程笔记或 Markdown 材料"
        rows={12}
      />
    </label>
  );
}
