'use client';

import React, { useCallback, useState, useRef } from 'react';
import { FileText, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  UPLOAD_ACCEPT,
  filterSupportedFiles,
  SUPPORTED_UPLOAD_LABEL,
} from '@/lib/uploads';

interface FileUploadProps {
  onFilesSelect: (files: File[]) => void;
  disabled?: boolean;
}

export function FileUpload({ onFilesSelect, disabled }: FileUploadProps) {
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

    const { accepted } = filterSupportedFiles(e.dataTransfer.files);
    if (accepted.length > 0) {
      onFilesSelect(accepted);
    }
  }, [disabled, onFilesSelect]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const { accepted } = filterSupportedFiles(files);
      if (accepted.length > 0) {
        onFilesSelect(accepted);
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
      className={cn(
        'relative border-2 border-dashed rounded-xl p-12 smooth-transition cursor-pointer',
        'flex flex-col items-center justify-center gap-4',
        isDragging
          ? 'border-black bg-gray-50 scale-105'
          : 'border-gray-300 hover:border-gray-500 hover:bg-gray-50',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={UPLOAD_ACCEPT}
        onChange={handleFileInput}
        disabled={disabled}
        style={{ display: 'none' }}
        multiple
      />

      <div className={cn(
        'rounded-full p-4 smooth-transition pointer-events-none',
        isDragging ? 'bg-gray-200' : 'bg-gray-100'
      )}>
        {isDragging ? (
          <Upload className="h-8 w-8 text-black" />
        ) : (
          <FileText className="h-8 w-8 text-gray-600" />
        )}
      </div>

      <div className="text-center pointer-events-none">
        <p className="text-sm font-semibold text-black mb-1">
          {isDragging
            ? 'Drop your procurement documents here'
            : 'Drag & drop your procurement documents here'}
        </p>
        <p className="text-xs text-gray-500">{SUPPORTED_UPLOAD_LABEL}</p>
      </div>
    </div>
  );
}
