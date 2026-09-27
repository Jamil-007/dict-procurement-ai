'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const LINKS = [
  { href: '/', label: 'Analyze' },
  { href: '/analyst', label: 'ProcAI' },
  { href: '/forms', label: 'Forms' },
  { href: '/items', label: 'Procurements' },
  { href: '/hub', label: 'Knowledge Hub' },
];

export function TopNav() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === '/' ? pathname === '/' : pathname.startsWith(href);

  return (
    <nav className="fixed top-4 right-4 z-50 flex items-center gap-1 rounded-full border border-zinc-200 bg-white/90 px-1 py-1 shadow-sm backdrop-blur">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={cn(
            'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
            isActive(link.href)
              ? 'bg-zinc-900 text-white'
              : 'text-zinc-500 hover:text-zinc-900'
          )}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
