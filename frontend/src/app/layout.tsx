import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LinkedIn Intelligence — Optimizá tu perfil tech con IA",
  description: "Analizamos miles de ofertas para darte recomendaciones exactas: qué skills agregar, cómo reescribir tu CV y dónde estás parado vs. los mejores.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
