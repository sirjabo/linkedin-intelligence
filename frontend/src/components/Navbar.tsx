"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Zap } from "lucide-react";

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
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/80 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/40">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white text-sm tracking-tight">
            LinkedIn<span className="text-blue-400">Intelligence</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                pathname === href
                  ? "bg-white/10 text-white font-medium"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
