import Link from "next/link";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { LayoutDashboard, ListChecks, Wrench, CheckCircle2 } from "lucide-react";


export default function Shell({ children }: { children: React.ReactNode }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white/60 dark:bg-neutral-900/60 sticky top-0 backdrop-blur">
        <div className="container flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-xl bg-brand" />
            <span className="font-semibold tracking-tight">Organization Console</span>
          </div>
          <nav className="hidden md:flex items-center gap-3">
            <Link href="/" className="btn btn-ghost focus-ring flex items-center gap-2">
              <LayoutDashboard className="size-4" /> Home
            </Link>
            <Link href="/tasks" className="btn btn-ghost focus-ring flex items-center gap-2">
              <ListChecks className="size-4" /> Tasks
            </Link>
            <Link href="/services" className="btn btn-ghost focus-ring flex items-center gap-2">
              <Wrench className="size-4" /> Services
            </Link>
            <Link href="/proofs" className="btn" aria-label="Proofs">
              <CheckCircle2 className="size-4" /> Proofs
            </Link>
            <Link href="/guide" className="btn btn-ghost focus-ring">Guide</Link>
          </nav>
          <div className="flex items-center gap-2">
            {mounted && (
              <button
                className="btn focus-ring"
                onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
                aria-label="Toggle theme"
              >
                {resolvedTheme === "dark" ? "Light" : "Dark"}
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="container py-6">{children}</main>
    </div>
  );
}