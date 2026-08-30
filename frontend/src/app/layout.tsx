import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LinkedIn Intelligence — Optimizá tu perfil tech con IA",
  description: "Analizamos miles de ofertas para darte recomendaciones exactas: qué skills agregar, cómo reescribir tu CV y dónde estás parado vs. los mejores.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Inject runtime env into window so the client bundle can read them even
  // when NEXT_PUBLIC_* vars were not available at Docker build time.
  const runtimeEnv = {
    SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    SUPABASE_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    API_URL: process.env.NEXT_PUBLIC_API_URL ?? "",
  };

  return (
    <html lang="es">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__ENV__=${JSON.stringify(runtimeEnv)};`,
          }}
        />
      </head>
      <body className={inter.className}>
        <AuthProvider>
          <main id="main-content">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
