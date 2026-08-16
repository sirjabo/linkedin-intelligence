"use client";
import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import CVUpload from "@/components/CVUpload";
import ChatInterface from "@/components/ChatInterface";
import CVPreview from "@/components/CVPreview";
import { CVData, SSEEvent } from "@/types/cv";
import { RotateCcw, Zap, Loader2 } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getSupabase } from "@/lib/supabase";

export default function CVPage() {
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [cvData, setCVData] = useState<CVData | null>(null);
  const [updatedSections, setUpdatedSections] = useState<string[]>([]);

  useEffect(() => {
    getSupabase().auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/auth");
      } else {
        setAuthChecked(true);
      }
    });
  }, [router]);

  useEffect(() => {
    if (updatedSections.length === 0) return;
    const t = setTimeout(() => setUpdatedSections([]), 3000);
    return () => clearTimeout(t);
  }, [updatedSections]);

  const handleReady = useCallback((id: string, data: CVData) => {
    setSessionId(id);
    setCVData(data);
  }, []);

  const handleCVUpdate = useCallback((section: string, event: SSEEvent) => {
    if (!section) return;

    setCVData((prev) => {
      if (!prev) return prev;
      const next = { ...prev };

      if (section === "summary" && typeof event.content === "string") {
        next.summary = event.content;
      } else if (section === "name" && typeof event.content === "string") {
        next.name = event.content;
      } else if (section === "target_role" && typeof event.content === "string") {
        next.target_role = event.content;
      } else if (section === "skills" && typeof event.content === "object" && event.content) {
        next.skills = event.content as CVData["skills"];
      } else if (section === "experience") {
        if (event.index !== undefined && event.field && Array.isArray(event.content)) {
          const expCopy = [...prev.experience];
          expCopy[event.index] = { ...expCopy[event.index], [event.field]: event.content };
          next.experience = expCopy;
        } else if (Array.isArray(event.content)) {
          next.experience = event.content as CVData["experience"];
        }
      } else if (section === "education" && Array.isArray(event.content)) {
        next.education = event.content as CVData["education"];
      } else if (section === "projects" && Array.isArray(event.content)) {
        next.projects = event.content as CVData["projects"];
      } else if (section === "certifications" && Array.isArray(event.content)) {
        next.certifications = event.content as CVData["certifications"];
      }

      return next;
    });

    setUpdatedSections((prev) => [...new Set([...prev, section])]);
  }, []);

  const handleReset = () => {
    setSessionId(null);
    setCVData(null);
    setUpdatedSections([]);
  };

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center" role="status" aria-label="Verificando sesión">
        <Loader2 className="w-6 h-6 text-blue-400 animate-spin" aria-hidden="true" />
      </div>
    );
  }

  if (!sessionId || !cvData) {
    return (
      <>
        <Navbar />
        <CVUpload onReady={handleReady} />
      </>
    );
  }

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      {/* Chat panel */}
      <div className="w-[400px] shrink-0 flex flex-col border-r border-white/10">
        <ChatInterface
          sessionId={sessionId}
          cvData={cvData}
          onCVUpdate={handleCVUpdate}
        />
      </div>

      {/* CV Preview panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-1.5 group">
              <div className="w-5 h-5 rounded-md bg-blue-600 flex items-center justify-center">
                <Zap className="w-3 h-3 text-white" />
              </div>
              <span className="text-xs text-slate-500 group-hover:text-slate-300 transition-colors hidden sm:block">LinkedIn Intelligence</span>
            </Link>
            <div className="w-px h-3 bg-white/10 hidden sm:block" />
            <div className="flex items-center gap-2" role="status">
              <div className="w-2 h-2 rounded-full bg-green-400" aria-hidden="true" />
              <span className="text-xs text-slate-400">CV actualizado automáticamente</span>
            </div>
          </div>
          <button
            onClick={handleReset}
            aria-label="Empezar con un nuevo CV"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <RotateCcw className="w-3 h-3" aria-hidden="true" />
            Nuevo CV
          </button>
        </div>

        {/* Preview */}
        <div className="flex-1 overflow-hidden">
          <CVPreview
            sessionId={sessionId}
            cvData={cvData}
            updatedSections={updatedSections}
          />
        </div>
      </div>
    </div>
  );
}
