'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Top-level product tabs — each team's deliverable lives under its own tab. */
const TABS = [
  { href: '/', label: 'Proc AI' },
  { href: '/compliance', label: 'Compliance Suite' },
];

export function NavTabs() {
  const pathname = usePathname();

  return (
    <header className="relative z-20 flex h-14 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/80 px-4 backdrop-blur">
      <div className="hidden items-center gap-2.5 md:flex">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-sm">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-slate-900">
          Procurement AI
        </span>
        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
          BETA
        </span>
      </div>

      <nav className="absolute left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-slate-100 p-1">
        {TABS.map((tab) => {
          const active =
            tab.href === '/'
              ? pathname === '/'
              : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                'rounded-full px-4 py-1.5 text-sm font-medium transition-all',
                active
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {/* Right side is reserved for the Past Reviews trigger. */}
      <div className="w-32" />
    </header>
  );
}
