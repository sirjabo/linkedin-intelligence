"use client";
import { useState, useRef } from "react";
import { Upload, FileText, Loader2, X } from "lucide-react";
import { uploadCV, createCVFromText } from "@/lib/api";
import { CVData } from "@/types/cv";

interface Props {
  onReady: (sessionId: string, cvData: CVData) => void;
}

export default function CVUpload({ onReady }: Props) {
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const addFiles = (incoming: FileList | File[]) => {
    const pdfs = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) { setError("Solo se aceptan archivos PDF."); return; }
    setError("");
    setSelectedFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...pdfs.filter((f) => !names.has(f.name))];
    });
  };

  const removeFile = (name: string) =>
    setSelectedFiles((prev) => prev.filter((f) => f.name !== name));

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const res = await uploadCV(selectedFiles);
      onReady(res.id, res.cv_data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al subir los archivos");
    } finally {
      setLoading(false);
    }
  };

  const handlePaste = async () => {
    if (!pasteText.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await createCVFromText(pasteText);
      onReady(res.id, res.cv_data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al procesar el texto");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 mb-5 shadow-lg shadow-blue-900/50">
            <FileText className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">CV Intelligence</h1>
          <p className="text-blue-200/80 text-base">
            Subí tu CV y un coach de IA lo optimizará para ATS y reclutadores
          </p>
        </div>

        {/* Mode toggle */}
        <div className="flex bg-white/5 rounded-xl p-1 mb-6 border border-white/10">
          {(["upload", "paste"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                mode === m
                  ? "bg-blue-600 text-white shadow"
                  : "text-blue-200/70 hover:text-white"
              }`}
            >
              {m === "upload" ? "📎 Subir PDF" : "📋 Pegar texto"}
            </button>
          ))}
        </div>

        {/* Upload zone */}
        {mode === "upload" ? (
          <div className="space-y-3">
            <div
              onClick={() => !loading && fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
              }}
              className={`
                relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
                transition-all duration-200
                ${dragging
                  ? "border-blue-400 bg-blue-600/10 scale-[1.02]"
                  : "border-white/20 bg-white/5 hover:border-blue-500/50 hover:bg-white/[0.07]"
                }
              `}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                multiple
                className="hidden"
                onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }}
              />
              <div className="flex flex-col items-center gap-3 text-blue-200/70">
                <Upload className="w-10 h-10" />
                <div>
                  <p className="text-base font-medium text-white/80">Arrastrá tus CVs aquí</p>
                  <p className="text-sm mt-1">o hacé click para seleccionar — podés subir varios PDFs</p>
                </div>
                <p className="text-xs text-blue-300/50 mt-1">Solo archivos PDF</p>
              </div>
            </div>

            {selectedFiles.length > 0 && (
              <div className="space-y-2">
                {selectedFiles.map((f) => (
                  <div key={f.name} className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5">
                    <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                    <span className="text-sm text-white/80 flex-1 truncate">{f.name}</span>
                    <span className="text-xs text-blue-300/50 shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => removeFile(f.name)} className="text-slate-500 hover:text-red-400 transition-colors ml-1">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={handleUpload}
                  disabled={loading}
                  className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-all flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Analizando con IA...</>
                  ) : (
                    `Analizar ${selectedFiles.length > 1 ? `${selectedFiles.length} PDFs` : "PDF"} con IA`
                  )}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Pegá el texto de tu CV aquí..."
              rows={10}
              className="w-full bg-white/5 border border-white/15 rounded-xl p-4 text-white/90 text-sm placeholder-blue-200/30 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all"
            />
            <button
              onClick={handlePaste}
              disabled={!pasteText.trim() || loading}
              className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Analizando...</>
              ) : (
                "Analizar con IA"
              )}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
