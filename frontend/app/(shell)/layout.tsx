// The merged app reuses the top-nav from the root layout instead of feature/mark's
// sidebar shell. This layout gives /items and /hub a centered container
// with top padding so their content clears the floating top-nav (they were
// originally designed to sit next to a full-height sidebar).
export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-page text-ink">
      <div className="mx-auto max-w-6xl px-6 pb-16 pt-20">{children}</div>
    </main>
  );
}
