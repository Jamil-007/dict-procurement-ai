'use client';

import React, { useState } from 'react';
import { Paperclip, ArrowUp, X, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface InputAreaProps {
  onFileSelect: (file: File) => void;
  onRemoveFile: (index: number) => void;
  onSend: (message: string) => void;
  selectedFiles: File[];
  disabled?: boolean;
  isSplitView?: boolean;
  placeholder?: string;
}

export function InputArea({
  onFileSelect,
  onRemoveFile,
  onSend,
  selectedFiles,
  disabled,
  isSplitView,
  placeholder = 'Ask about procurement documents...'
}: InputAreaProps) {
  const [message, setMessage] = useState('');

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      // Add new files to the existing selection
      Array.from(files).forEach(file => onFileSelect(file));
      // Reset the input so the same file can be selected again if needed
      e.target.value = '';
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
        <form onSubmit={handleSubmit} className="relative space-y-3">
          {/* Selected Files Display */}
          {selectedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 bg-gray-100 rounded-full px-3 py-2 text-sm"
                >
                  <FileText className="h-4 w-4 text-gray-600" />
                  <span className="text-gray-800 max-w-[200px] truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => onRemoveFile(index)}
                    className="hover:bg-gray-200 rounded-full p-1 transition-colors"
                  >
                    <X className="h-3 w-3 text-gray-600" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input Area */}
          <div className="flex items-center gap-2 bg-white rounded-full border-2 border-gray-300 hover:border-gray-400 focus-within:border-black smooth-transition p-3 px-4">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 hover:bg-gray-100 rounded-full"
              onClick={() => !disabled && document.getElementById('input-file-upload')?.click()}
              disabled={disabled}
            >
              <Paperclip className="h-5 w-5 text-gray-600" />
            </Button>

            <input
              id="input-file-upload"
              type="file"
              accept=".pdf"
              onChange={handleFileInput}
              disabled={disabled}
              className="hidden"
              multiple
            />

            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              disabled={disabled}
              placeholder={placeholder}
              className={cn(
                'flex-1 bg-transparent border-none outline-none text-sm',
                'placeholder:text-gray-400',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            />

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
