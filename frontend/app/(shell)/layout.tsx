import { AppSidebar } from "@/components/shell/app-sidebar";

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-page text-ink print:block print:h-auto print:overflow-visible">
      <AppSidebar />
      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
