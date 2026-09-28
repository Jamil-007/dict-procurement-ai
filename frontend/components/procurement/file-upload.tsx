'use client';

import React, { useCallback, useState, useRef } from 'react';
import { FolderOpen, UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  onFilesSelect: (files: File[]) => void;
  disabled?: boolean;
  className?: string;
}

export function FileUpload({ onFilesSelect, disabled, className }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled) return;

    const pdfFiles = Array.from(e.dataTransfer.files).filter(
      (file) => file.type === 'application/pdf'
    );
    if (pdfFiles.length > 0) {
      onFilesSelect(pdfFiles);
    }
  }, [disabled, onFilesSelect]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const pdfFiles = Array.from(files).filter((file) => file.type === 'application/pdf');
      if (pdfFiles.length > 0) {
        onFilesSelect(pdfFiles);
      }
      e.target.value = '';
    }
  }, [onFilesSelect]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      className={cn(
        'relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors',
        isDragging
          ? 'border-brand bg-sky scale-[1.01]'
          : 'border-line bg-sky/40 hover:border-brand/40 hover:bg-sky',
        disabled && 'cursor-not-allowed opacity-50',
        className
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileInput}
        disabled={disabled}
        style={{ display: 'none' }}
        multiple
      />

      <div className="grid h-14 w-14 place-items-center rounded-full bg-white pointer-events-none">
        <UploadCloud className="h-6 w-6 text-brand" />
      </div>

      <div className="pointer-events-none">
        <p className="text-[15px] font-semibold text-navy">
          {isDragging ? 'Drop your PDF here' : 'Drag and drop a PDF file here'}
        </p>
        <p className="mt-1 text-[13px] text-subtle">or click to browse</p>
      </div>

      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        className="pointer-events-none mt-1 flex items-center gap-2 rounded-md bg-brand px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-navy disabled:opacity-60"
      >
        <FolderOpen className="h-4 w-4" />
        Browse Files
      </button>

      <p className="pointer-events-none mt-1 text-[12px] text-subtle">
        Only PDF files are supported (max 50 MB)
      </p>
    </div>
  );
}
