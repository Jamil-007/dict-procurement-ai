/**
 * The page heading sits inline on the page background — not in a bar. Matches
 * `pageHead()` in html-proto/ai-analyst.html.
 */
export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-4">
      <div>
        <h1 className="text-[21px] font-bold tracking-tight text-zinc-900">{title}</h1>
        {subtitle && (
          <p className="mt-1 max-w-2xl text-[13px] text-subtle">{subtitle}</p>
        )}
      </div>
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  );
}

/** Shared control styling, lifted from the prototype's UI atoms. */
export const btnPrimary =
  "rounded-md bg-brand px-4 py-2 text-[13px] font-semibold text-white hover:bg-navy transition-colors disabled:opacity-60";

export const btnGhost =
  "rounded-md border border-line bg-white px-3.5 py-2 text-[13px] font-medium text-ink hover:bg-sky transition-colors disabled:opacity-60";

export const btnDanger =
  "rounded-md bg-red-600 px-4 py-2 text-[13px] font-semibold text-white hover:bg-red-700 disabled:opacity-60";

export const inputCls =
  "w-full rounded-md border border-line bg-white px-3 py-2 text-[13px] text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15";

export const areaCls = `${inputCls} leading-relaxed resize-y`;

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold tracking-[0.13em] text-subtle">
      {children}
    </div>
  );
}
