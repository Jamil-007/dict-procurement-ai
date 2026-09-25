import React from 'react';
import { cn } from '@/lib/utils';

interface ChatLayoutProps {
  children: React.ReactNode;
  /** Pinned to the bottom of the column, outside the scroll area. */
  footer?: React.ReactNode;
  className?: string;
}

export function ChatLayout({ children, footer, className }: ChatLayoutProps) {
  return (
    <div className={cn('h-full min-h-0 bg-white flex flex-col', className)}>
      {/* Scrollable conversation */}
      <main className="flex-1 min-h-0 overflow-y-auto">
        <div className="w-full max-w-3xl mx-auto px-4 py-8">{children}</div>
      </main>

      {footer && <div className="shrink-0">{footer}</div>}
    </div>
  );
}
