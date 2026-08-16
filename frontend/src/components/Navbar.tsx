"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Zap, LogOut, User, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getSupabase } from "@/lib/supabase";

const links = [
  { href: "/profile", label: "Mi Perfil" },
  { href: "/analyze", label: "LinkedIn" },
  { href: "/skills", label: "Skills Radar" },
  { href: "/market", label: "Mercado" },
  { href: "/recommendations", label: "Ofertas" },
  { href: "/applications", label: "Postulaciones" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    getSupabase().auth.getSession().then(({ data: { session } }) => {
      setUserEmail(session?.user?.email ?? null);
    });
    const { data: { subscription } } = getSupabase().auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user?.email ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = async () => {
    await getSupabase().auth.signOut();
    router.push("/auth");
  };

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-blue-600 focus:px-3 focus:py-1.5 focus:text-sm focus:text-white focus:ring-2 focus:ring-white"
      >
        Saltar al contenido
      </a>

      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 group rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            aria-label="LinkedIn Intelligence — inicio"
          >
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/40">
              <Zap className="w-4 h-4 text-white" aria-hidden="true" />
            </div>
            <span className="font-semibold text-white text-sm tracking-tight">
              LinkedIn<span className="text-blue-400">Intelligence</span>
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Navegación principal">
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={pathname === href ? "page" : undefined}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  pathname === href
                    ? "bg-white/10 text-white font-medium"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                {label}
              </Link>
            ))}
            {userEmail && (
              <div className="flex items-center gap-2 ml-2 pl-2 border-l border-white/10">
                <div className="flex items-center gap-1.5 text-xs text-slate-400" aria-hidden="true">
                  <User className="w-3.5 h-3.5" aria-hidden="true" />
                  <span className="hidden sm:block max-w-[120px] truncate">{userEmail}</span>
                </div>
                <button
                  onClick={handleLogout}
                  aria-label="Cerrar sesión"
                  className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-white/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            )}
          </nav>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label={mobileOpen ? "Cerrar menú" : "Abrir menú"}
            aria-expanded={mobileOpen}
            aria-controls="mobile-menu"
          >
            {mobileOpen ? (
              <X className="w-5 h-5" aria-hidden="true" />
            ) : (
              <Menu className="w-5 h-5" aria-hidden="true" />
            )}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <nav
            id="mobile-menu"
            aria-label="Navegación móvil"
            className="md:hidden border-t border-white/10 bg-slate-950 px-4 py-3 space-y-1"
          >
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={pathname === href ? "page" : undefined}
                className={`block px-3 py-2 rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  pathname === href
                    ? "bg-white/10 text-white font-medium"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                {label}
              </Link>
            ))}
            {userEmail && (
              <div className="mt-2 pt-2 border-t border-white/10 flex items-center justify-between">
                <span className="text-xs text-slate-500 truncate max-w-[200px]">{userEmail}</span>
                <button
                  onClick={handleLogout}
                  aria-label="Cerrar sesión"
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-400 transition-colors px-2 py-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
                  Salir
                </button>
              </div>
            )}
          </nav>
        )}
      </header>
    </>
  );
}
