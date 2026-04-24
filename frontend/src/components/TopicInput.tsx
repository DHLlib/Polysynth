import { useEffect, useState } from "react";
import { Play, Paperclip } from "lucide-react";
import { FileUploadZone } from "./FileUploadZone";

interface Props {
  onSubmit: (topic: string, files: File[]) => void;
  disabled: boolean;
  value?: string;
}

export default function TopicInput({ onSubmit, disabled, value }: Props) {
  const [topic, setTopic] = useState(value || "");
  const [files, setFiles] = useState<File[]>([]);
  const [showUpload, setShowUpload] = useState(false);
  const isReadOnly = value !== undefined;

  useEffect(() => {
    if (value !== undefined) setTopic(value);
  }, [value]);

  const handleSubmit = () => {
    if (!topic.trim() || disabled || isReadOnly) return;
    onSubmit(topic.trim(), files);
    setFiles([]);
    setShowUpload(false);
  };

  if (isReadOnly) {
    return (
      <div className="flex-1 max-w-2xl flex items-center">
        <span className="text-sm text-text-secondary truncate">
          {value}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 flex-1 max-w-2xl">
      <div className="flex gap-2">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          placeholder="输入讨论话题..."
          disabled={disabled}
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-4 py-2 text-sm text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => setShowUpload((v) => !v)}
          disabled={disabled}
          className="relative bg-bg-secondary border border-border hover:bg-bg-tertiary text-text-secondary px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 disabled:opacity-50 transition-colors"
          title="添加附件"
        >
          <Paperclip size={16} />
          {files.length > 0 && (
            <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 bg-accent text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              {files.length}
            </span>
          )}
        </button>
        <button
          onClick={handleSubmit}
          disabled={disabled || !topic.trim()}
          className="bg-accent hover:bg-accent/90 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Play size={14} />
          开始
        </button>
      </div>
      {showUpload && (
        <FileUploadZone files={files} onChange={setFiles} />
      )}
    </div>
  );
}
