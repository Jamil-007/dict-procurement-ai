// The merged app reuses the top-nav from the root layout instead of feature/mark's
// sidebar shell. This layout is now a plain container so /items, /hub and /analyst
// render under the same top-nav as the rest of the app.
export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-page text-ink">{children}</main>
  );
}
