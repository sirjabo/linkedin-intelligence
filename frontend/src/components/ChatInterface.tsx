"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Bot, User, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { chatStream } from "@/lib/api";
import { ChatMessage, CVData, SSEEvent } from "@/types/cv";
import clsx from "clsx";

interface Props {
  sessionId: string;
  cvData: CVData;
  onCVUpdate: (section: string, update: SSEEvent) => void;
}

const SUGGESTIONS = [
  "Analizá mi CV y decime qué mejorar",
  "Optimizá mi summary para ser más impactante",
  "Mejoré los bullet points de mi experiencia más reciente",
  "Hacé que sea 100% compatible con ATS",
  "Agregá métricas y números a mis logros",
  "Optimizalo para un rol de Tech Lead en una startup",
];

export default function ChatInterface({ sessionId, cvData, onCVUpdate }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: `¡Hola! 👋 Ya analicé tu CV de **${cvData.name || "tu perfil"}**.\n\nEstoy listo para ayudarte a mejorarlo. Puedo:\n- ✍️ Reescribir secciones para que sean más impactantes\n- 🎯 Optimizar keywords para ATS\n- 📊 Agregar métricas y logros cuantificables\n- 💼 Adaptar el CV para roles o empresas específicas\n\n¿Por dónde empezamos?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || streaming) return;
    setInput("");

    const userMsg: ChatMessage = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);

    // Placeholder for streaming assistant response
    const assistantId = Date.now().toString();
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", id: assistantId },
    ]);

    try {
      const stream = await chatStream(sessionId, msg);
      const reader = stream.getReader();
      let buffer = "";
      let assistantText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += value;

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const event: SSEEvent = JSON.parse(raw);
            if (event.type === "text" && event.content) {
              assistantText += event.content;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: assistantText } : m
                )
              );
            } else if (event.type === "cv_update") {
              onCVUpdate(event.section ?? "", event);
            } else if (event.type === "done") {
              break;
            }
          } catch {
            // ignore malformed events
          }
        }
      }
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: "Ocurrió un error. Por favor intentá de nuevo." }
            : m
        )
      );
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/10 bg-slate-900 shrink-0">
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="text-white text-sm font-semibold">Coach de CV IA</p>
          <p className="text-blue-300/60 text-xs">Powered by Claude</p>
        </div>
        <div className="ml-auto w-2 h-2 rounded-full bg-green-400 animate-pulse" />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={msg.id ?? i}
            className={clsx(
              "flex gap-3 max-w-full",
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            )}
          >
            {/* Avatar */}
            <div
              className={clsx(
                "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                msg.role === "user"
                  ? "bg-blue-600"
                  : "bg-slate-700 ring-1 ring-white/10"
              )}
            >
              {msg.role === "user" ? (
                <User className="w-3.5 h-3.5 text-white" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-blue-300" />
              )}
            </div>

            {/* Bubble */}
            <div
              className={clsx(
                "rounded-2xl px-4 py-2.5 max-w-[85%] text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-tr-sm"
                  : "bg-slate-800 text-slate-100 rounded-tl-sm"
              )}
            >
              {msg.role === "assistant" ? (
                msg.content ? (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2">{children}</ul>,
                      li: ({ children }) => <li className="text-slate-200">{children}</li>,
                      strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                      code: ({ children }) => <code className="bg-slate-700 px-1 rounded text-blue-300 text-xs">{children}</code>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Pensando...
                  </span>
                )
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (only when not streaming and few messages) */}
      {!streaming && messages.length <= 2 && (
        <div className="px-4 pb-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleSend(s)}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-800 text-blue-300 border border-white/10 hover:bg-slate-700 hover:border-blue-500/30 transition-all"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-4 pb-4 pt-2 bg-slate-950 border-t border-white/10 shrink-0">
        <div className="flex items-end gap-2 bg-slate-800 rounded-2xl px-4 py-3 border border-white/10 focus-within:border-blue-500/50 transition-all">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pedile algo al coach... (Enter para enviar)"
            rows={1}
            disabled={streaming}
            className="flex-1 bg-transparent text-white text-sm placeholder-slate-500 resize-none outline-none leading-relaxed max-h-32 overflow-y-auto disabled:opacity-50"
            style={{ scrollbarWidth: "none" }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || streaming}
            className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center disabled:opacity-40 hover:bg-blue-500 transition-all shrink-0 mb-0.5"
          >
            {streaming ? (
              <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5 text-white" />
            )}
          </button>
        </div>
        <p className="text-center text-slate-600 text-[10px] mt-2">
          El CV se actualiza automáticamente con cada mejora
        </p>
      </div>
    </div>
  );
}
