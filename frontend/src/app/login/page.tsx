"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { login as apiLogin, forgotPassword } from "@/lib/api-v2";

type Mode = "signin" | "forgot" | "forgot-sent";

export default function LoginPage() {
  const { setTokens } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "forgot") {
        await forgotPassword(email);
        setMode("forgot-sent");
      } else {
        const data = await apiLogin(email, password);
        setTokens(data.access_token, data.refresh_token);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al procesar la solicitud");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">LinkedIn Intelligence</h1>
          <p className="text-slate-400 mt-2">
            {mode === "signin" ? "Iniciá sesión en tu cuenta" : "Recuperar contraseña"}
          </p>
        </div>

        <div className="bg-slate-900 rounded-2xl p-8 border border-slate-800">
          {mode === "forgot-sent" ? (
            <div className="text-center space-y-4">
              <div className="text-4xl">📧</div>
              <p className="text-white font-medium">Revisá tu email</p>
              <p className="text-slate-400 text-sm">
                Si existe una cuenta con <strong className="text-slate-300">{email}</strong>, te enviamos un link
                para resetear tu contraseña (expira en 15 minutos).
              </p>
              <p className="text-slate-500 text-xs">Revisá también la carpeta de spam.</p>
              <button
                onClick={() => { setMode("signin"); setError(""); }}
                className="w-full mt-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                ← Volver al inicio de sesión
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
              {error && (
                <div className="bg-red-900/30 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                  placeholder="tu@email.com"
                />
              </div>

              {mode === "signin" && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-slate-300">Contraseña</label>
                    <button
                      type="button"
                      onClick={() => { setMode("forgot"); setError(""); }}
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                    placeholder="••••••••"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition-colors"
              >
                {loading
                  ? mode === "forgot" ? "Enviando..." : "Iniciando sesión..."
                  : mode === "forgot" ? "Enviar link de recuperación" : "Iniciar sesión"}
              </button>

              {mode === "forgot" && (
                <button
                  type="button"
                  onClick={() => { setMode("signin"); setError(""); }}
                  className="w-full text-center text-sm text-slate-400 hover:text-white transition-colors"
                >
                  ← Volver al inicio de sesión
                </button>
              )}

              {mode === "signin" && (
                <p className="text-center text-sm text-slate-400">
                  ¿No tenés cuenta?{" "}
                  <Link href="/register" className="text-blue-400 hover:text-blue-300">
                    Registrate
                  </Link>
                </p>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
