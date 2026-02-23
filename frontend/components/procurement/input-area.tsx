'use client';

import React, { useState, useRef } from 'react';
import { Paperclip, ArrowUp, X, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface InputAreaProps {
  onFilesSelect: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  onSend: (message: string) => void;
  selectedFiles: File[];
  disabled?: boolean;
  isSplitView?: boolean;
  placeholder?: string;
  fileOnly?: boolean;
}

export function InputArea({
  onFilesSelect,
  onRemoveFile,
  onSend,
  selectedFiles,
  disabled,
  isSplitView,
  placeholder = 'Ask about procurement documents...',
  fileOnly = false,
}: InputAreaProps) {
  const [message, setMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      onFilesSelect(Array.from(files));
      // Reset the input so the same file can be selected again if needed
      e.target.value = '';
    }
  };

  const handleFileButtonClick = (e: React.MouseEvent) => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((message.trim() || selectedFiles.length > 0) && !disabled) {
      onSend(message);
      setMessage('');
    }
  };

  return (
    <div className={cn(
      'p-4 bg-white border-t border-gray-200',
      isSplitView ? 'absolute bottom-0 left-0 right-0' : 'fixed bottom-0 left-0 right-0'
    )}>
      <div className="max-w-3xl mx-auto">
        <form onSubmit={handleSubmit} className="relative">
          {/* Input Area */}
          <div className="flex items-center gap-2 bg-white rounded-full border-2 border-gray-300 hover:border-gray-400 focus-within:border-black smooth-transition p-3 px-4">
            {fileOnly && (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="shrink-0 hover:bg-gray-100 rounded-full"
                  onClick={handleFileButtonClick}
                  disabled={disabled}
                >
                  <Paperclip className="h-5 w-5 text-gray-600" />
                </Button>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileInput}
                  disabled={disabled}
                  style={{ display: 'none' }}
                  multiple
                />
              </>
            )}

            {/* Show file chips inline OR text input, not both */}
            {selectedFiles.length > 0 ? (
              <div className="flex-1 flex items-center gap-2 min-w-0">
                {selectedFiles.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 bg-gray-100 rounded-full px-3 py-1.5 text-sm"
                  >
                    <FileText className="h-4 w-4 text-gray-600 shrink-0" />
                    <span className="text-gray-800 max-w-[200px] truncate">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => onRemoveFile(index)}
                      className="hover:bg-gray-200 rounded-full p-0.5 transition-colors"
                    >
                      <X className="h-3 w-3 text-gray-600" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <input
                type="text"
                value={message}
                onChange={(e) => !fileOnly && setMessage(e.target.value)}
                disabled={disabled}
                readOnly={fileOnly}
                placeholder={placeholder}
                className={cn(
                  'flex-1 bg-transparent border-none outline-none text-sm',
                  'placeholder:text-gray-400',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  fileOnly && 'cursor-default'
                )}
                onClick={fileOnly ? handleFileButtonClick : undefined}
              />
            )}

            <Button
              type="submit"
              size="icon"
              disabled={disabled || (!message.trim() && selectedFiles.length === 0)}
              className="shrink-0 rounded-full bg-black hover:bg-gray-800 smooth-transition"
            >
              <ArrowUp className="h-5 w-5" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
