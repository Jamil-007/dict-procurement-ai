"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { LayoutList, Library, MessageSquare, ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/items", label: "Procurements", icon: LayoutList },
  { href: "/", label: "ProcAI", icon: MessageSquare },
  { href: "/hub", label: "Knowledge Hub", icon: Library },
];

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "relative shrink-0 bg-navy text-white flex flex-col transition-[width] duration-200",
        collapsed ? "w-[68px]" : "w-[232px]",
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((value) => !value)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!collapsed}
        className="absolute -right-3 top-6 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-navy text-white/70 shadow-md transition-colors hover:bg-brand hover:text-white"
      >
        <ChevronLeft
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-200",
            collapsed && "rotate-180",
          )}
        />
      </button>

      <Link
        href="/items"
        className={cn(
          "flex items-center gap-2.5 px-4 py-4",
          collapsed && "justify-center px-0",
        )}
      >
        <Image
          src="/dict-logo.png"
          alt=""
          width={28}
          height={28}
          className="rounded shrink-0"
        />
        {!collapsed && (
          <span className="block text-[13.5px] font-bold leading-tight tracking-wide">
            Procurement
            <br />
            Intelligence Platform
          </span>
        )}
      </Link>

      {!collapsed && (
        <p className="px-4 pt-4 pb-2 text-[11px] font-semibold tracking-[0.12em] text-white/40">
          WORKSPACE
        </p>
      )}

      <nav className={cn("space-y-0.5", collapsed ? "px-2 pt-3" : "px-2")}>
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors",
                collapsed && "justify-center px-0",
                active
                  ? "bg-white/15 font-semibold text-white"
                  : "text-white/70 hover:bg-white/10",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && label}
            </Link>
          );
        })}
      </nav>

      <div
        className={cn(
          "mt-auto border-t border-white/10 py-3.5",
          collapsed ? "px-0" : "px-4",
        )}
      >
        <div
          className={cn(
            "flex items-center gap-2.5",
            collapsed && "justify-center",
          )}
        >
          <span
            title={collapsed ? "BAC Admin" : undefined}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/15 text-[12px] font-semibold"
          >
            BA
          </span>
          {!collapsed && (
            <span>
              <span className="block text-[13px] font-medium">BAC Admin</span>
              <span className="block text-[11px] text-white/50">
                Bids and Awards Committee
              </span>
            </span>
          )}
        </div>
      </div>
    </aside>
  );
}
