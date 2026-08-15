"use client";
import { useState } from "react";
import { Download, Loader2, Mail, Phone, MapPin, Linkedin, Github, Globe } from "lucide-react";
import { CVData } from "@/types/cv";
import { getPdfUrl } from "@/lib/api";
import clsx from "clsx";

interface Props {
  sessionId: string;
  cvData: CVData;
  updatedSections: string[];
}

export default function CVPreview({ sessionId, cvData, updatedSections }: Props) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const url = getPdfUrl(sessionId);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${cvData.name || "cv"}_optimizado.pdf`;
      a.click();
    } finally {
      setTimeout(() => setDownloading(false), 2000);
    }
  };

  const isUpdated = (section: string) => updatedSections.includes(section);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 bg-gray-50 border-b border-gray-200 shrink-0">
        <span className="text-sm font-medium text-gray-600">Preview del CV</span>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-navy text-white text-sm font-medium hover:bg-blue-900 disabled:opacity-50 transition-all shadow-sm"
          style={{ backgroundColor: "#1a365d" }}
        >
          {downloading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          Descargar PDF
        </button>
      </div>

      {/* CV Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[700px] mx-auto">
          {/* Header */}
          <div
            className={clsx(
              "px-8 py-7 transition-all duration-500",
              isUpdated("name") || isUpdated("contact") || isUpdated("target_role")
                ? "ring-2 ring-yellow-400 ring-inset"
                : ""
            )}
            style={{ backgroundColor: "#1a365d" }}
          >
            <h1 className="text-2xl font-bold text-white leading-tight">
              {cvData.name || "Tu Nombre"}
            </h1>
            {cvData.target_role && (
              <p className="text-blue-200 mt-1 text-sm font-medium">{cvData.target_role}</p>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
              {cvData.contact?.email && (
                <ContactItem icon={<Mail className="w-3 h-3" />} text={cvData.contact.email} />
              )}
              {cvData.contact?.phone && (
                <ContactItem icon={<Phone className="w-3 h-3" />} text={cvData.contact.phone} />
              )}
              {cvData.contact?.location && (
                <ContactItem icon={<MapPin className="w-3 h-3" />} text={cvData.contact.location} />
              )}
              {cvData.contact?.linkedin && (
                <ContactItem icon={<Linkedin className="w-3 h-3" />} text={cvData.contact.linkedin} />
              )}
              {cvData.contact?.github && (
                <ContactItem icon={<Github className="w-3 h-3" />} text={cvData.contact.github} />
              )}
              {cvData.contact?.website && (
                <ContactItem icon={<Globe className="w-3 h-3" />} text={cvData.contact.website} />
              )}
            </div>
          </div>

          <div className="px-8 py-5 space-y-5">
            {/* Summary */}
            {cvData.summary && (
              <Section title="Resumen Profesional" updated={isUpdated("summary")}>
                <p className="text-gray-700 text-sm leading-relaxed">{cvData.summary}</p>
              </Section>
            )}

            {/* Experience */}
            {cvData.experience.length > 0 && (
              <Section title="Experiencia" updated={isUpdated("experience")}>
                <div className="space-y-4">
                  {cvData.experience.map((exp, i) => (
                    <div key={i}>
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-gray-900 text-sm">{exp.company}</span>
                        <span className="text-xs text-gray-400 whitespace-nowrap shrink-0">
                          {exp.start_date} – {exp.end_date}
                        </span>
                      </div>
                      <p className="text-blue-700 text-sm font-medium italic mb-1">{exp.role}</p>
                      {exp.bullets.length > 0 && (
                        <ul className="space-y-0.5">
                          {exp.bullets.map((b, j) => (
                            <li key={j} className="text-sm text-gray-600 flex gap-2">
                              <span className="text-blue-500 mt-0.5 shrink-0">•</span>
                              <span>{b}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Skills */}
            {Object.values(cvData.skills).some((arr) => arr.length > 0) && (
              <Section title="Habilidades Técnicas" updated={isUpdated("skills")}>
                <div className="space-y-1.5">
                  {[
                    { label: "Lenguajes", vals: cvData.skills.languages },
                    { label: "Frameworks", vals: cvData.skills.frameworks },
                    { label: "Cloud & DevOps", vals: cvData.skills.cloud },
                    { label: "Bases de datos", vals: cvData.skills.databases },
                    { label: "Herramientas", vals: cvData.skills.tools },
                    { label: "Otros", vals: cvData.skills.other },
                  ]
                    .filter((r) => r.vals.length > 0)
                    .map((row) => (
                      <div key={row.label} className="flex gap-2 text-sm">
                        <span className="font-semibold text-gray-800 w-28 shrink-0">
                          {row.label}:
                        </span>
                        <span className="text-gray-600">{row.vals.join(", ")}</span>
                      </div>
                    ))}
                </div>
              </Section>
            )}

            {/* Education */}
            {cvData.education.length > 0 && (
              <Section title="Educación" updated={isUpdated("education")}>
                <div className="space-y-3">
                  {cvData.education.map((edu, i) => (
                    <div key={i}>
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-gray-900 text-sm">
                          {edu.degree}{edu.field ? ` en ${edu.field}` : ""}
                        </span>
                        <span className="text-xs text-gray-400 shrink-0">{edu.year}</span>
                      </div>
                      <p className="text-blue-700 text-sm font-medium italic">{edu.institution}</p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Projects */}
            {cvData.projects.length > 0 && (
              <Section title="Proyectos" updated={isUpdated("projects")}>
                <div className="space-y-3">
                  {cvData.projects.map((proj, i) => (
                    <div key={i}>
                      <p className="font-semibold text-gray-900 text-sm">{proj.name}</p>
                      <p className="text-gray-600 text-sm">{proj.description}</p>
                      {proj.technologies.length > 0 && (
                        <p className="text-xs text-gray-400 italic mt-0.5">
                          Stack: {proj.technologies.join(", ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Certifications */}
            {cvData.certifications.length > 0 && (
              <Section title="Certificaciones" updated={isUpdated("certifications")}>
                <div className="space-y-1">
                  {cvData.certifications.map((cert, i) => (
                    <p key={i} className="text-sm text-gray-700">
                      <span className="font-medium">{cert.name}</span>
                      {cert.issuer && ` — ${cert.issuer}`}
                      {cert.year && ` (${cert.year})`}
                    </p>
                  ))}
                </div>
              </Section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ContactItem({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-1.5 text-blue-100/80 text-xs">
      {icon}
      <span>{text}</span>
    </div>
  );
}

function Section({
  title,
  children,
  updated,
}: {
  title: string;
  children: React.ReactNode;
  updated: boolean;
}) {
  return (
    <div
      className={clsx(
        "transition-all duration-500 rounded-md",
        updated ? "ring-2 ring-yellow-400 ring-offset-2" : ""
      )}
    >
      <div className="flex items-center gap-3 mb-2">
        <h2
          className="text-[10px] font-bold tracking-widest uppercase"
          style={{ color: "#1a365d" }}
        >
          {title}
        </h2>
        <div className="flex-1 h-px" style={{ backgroundColor: "#4299e1" }} />
      </div>
      {children}
    </div>
  );
}
