import { useState, useRef, useCallback } from 'react';

interface Props {
  onFile: (file: File) => void;
  label?: string;
  accept?: string;
  id: string;
}

export default function FileUpload({ onFile, label = 'Upload EDI File', accept = '.edi,.txt,.dat,.x12', id }: Props) {
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        setFileName(file.name);
        onFile(file);
      }
    },
    [onFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setFileName(file.name);
        onFile(file);
      }
    },
    [onFile],
  );

  return (
    <div
      id={id}
      className={`drop-zone p-8 text-center cursor-pointer transition-all duration-300 ${dragging ? 'active' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      <div className="flex flex-col items-center gap-3">
        <div className="w-14 h-14 rounded-full flex items-center justify-center bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <div>
          <p className="text-[var(--text-primary)] font-medium">{label}</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {fileName ? (
              <span className="text-[var(--accent-cyan)]">{fileName}</span>
            ) : (
              'Drag & drop or click — .edi, .txt, .dat, .x12'
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
