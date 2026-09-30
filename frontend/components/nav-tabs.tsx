'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

/** Top-level product tabs — each team's deliverable lives under its own tab. */
const TABS = [
  { href: '/', label: 'Proc AI' },
  { href: '/compliance', label: 'Compliance & Data Integrity' },
];

export function NavTabs() {
  const pathname = usePathname();

  return (
    <header className="relative z-20 flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4">
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-black px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-white">
          Beta
        </span>
        <span className="hidden text-sm font-semibold tracking-tight text-gray-900 md:inline">
          DICT Procurement
        </span>
      </div>

      <nav className="flex items-center gap-1 rounded-full border border-gray-200 bg-white p-1">
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
                  ? 'bg-black text-white'
                  : 'text-gray-500 hover:text-gray-900'
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
