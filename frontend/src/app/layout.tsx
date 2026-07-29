import type { Metadata } from "next";
import { Outfit } from "next/font/google";

import { Providers } from "@/components/Providers";

import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "LinkedIn Intelligence",
  description: "Analizá tu CV y optimizá tu perfil para el mercado tech",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${outfit.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
