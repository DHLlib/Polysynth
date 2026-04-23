import { useCallback } from "react";
import { X, FileText, Upload } from "lucide-react";

interface FileUploadZoneProps {
  files: File[];
  onChange: (files: File[]) => void;
}

const MAX_FILES = 5;
const MAX_SIZE_MB = 20;
const ALLOWED_TYPES = [
  "text/plain",
  "text/markdown",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function FileUploadZone({ files, onChange }: FileUploadZoneProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const dropped = Array.from(e.dataTransfer.files);
      const valid = dropped.filter((f) => ALLOWED_TYPES.includes(f.type));
      const merged = [...files, ...valid].slice(0, MAX_FILES);
      onChange(merged);
    },
    [files, onChange]
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files || []);
      const merged = [...files, ...selected].slice(0, MAX_FILES);
      onChange(merged);
    },
    [files, onChange]
  );

  const removeFile = useCallback(
    (index: number) => {
      onChange(files.filter((_, i) => i !== index));
    },
    [files, onChange]
  );

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors cursor-pointer"
      >
        <Upload className="mx-auto h-8 w-8 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          拖拽文件到此处，或{" "}
          <label className="text-blue-600 cursor-pointer hover:underline">
            <input
              type="file"
              multiple
              accept=".txt,.md,.pdf,.docx,.xlsx,.pptx"
              className="hidden"
              onChange={handleSelect}
            />
            点击上传
          </label>
        </p>
        <p className="mt-1 text-xs text-gray-400">
          最多 {MAX_FILES} 个文件，单个不超过 {MAX_SIZE_MB}MB
        </p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between bg-gray-50 rounded px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-gray-500" />
                <span className="truncate max-w-[200px]">{file.name}</span>
                <span className="text-xs text-gray-400">{formatSize(file.size)}</span>
              </div>
              <button
                onClick={() => removeFile(idx)}
                className="text-gray-400 hover:text-red-500"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
