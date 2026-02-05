import React from 'react';
import { cn } from '@/lib/utils';

interface ChatLayoutProps {
  children: React.ReactNode;
  className?: string;
}

export function ChatLayout({ children, className }: ChatLayoutProps) {
  return (
    <div className={cn('h-full bg-white flex flex-col relative', className)}>
      {/* Main Content */}
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 py-8 pb-6 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
