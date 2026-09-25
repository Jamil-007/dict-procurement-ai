"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { LayoutList, Library, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/items", label: "All Items", icon: LayoutList },
  { href: "/analyst", label: "Procurement Analyst", icon: MessageSquare },
  { href: "/hub", label: "Knowledge Hub", icon: Library },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[232px] shrink-0 bg-navy text-white flex flex-col">
      <Link href="/items" className="flex items-center gap-2.5 px-4 py-4">
        <Image
          src="/dict-logo.png"
          alt=""
          width={28}
          height={28}
          className="rounded"
        />
        <span>
          <span className="block text-[15px] font-bold tracking-wide">
            AI Analyst
          </span>
          <span className="block text-[12px] text-white/55 leading-tight mt-0.5">
            DICT Procurement
          </span>
        </span>
      </Link>

      <p className="px-4 pt-4 pb-2 text-[11px] font-semibold tracking-[0.12em] text-white/40">
        WORKSPACE
      </p>

      <nav className="px-2 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors",
                active
                  ? "bg-white/15 font-semibold text-white"
                  : "text-white/70 hover:bg-white/10"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-white/10 px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/15 text-[12px] font-semibold">
            BA
          </span>
          <span>
            <span className="block text-[13px] font-medium">BAC Admin</span>
            <span className="block text-[11px] text-white/50">
              Bids and Awards Committee
            </span>
          </span>
        </div>
      </div>
    </aside>
  );
}
