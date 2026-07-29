import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number): string {
  if (score >= 75) return "text-green-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

export function scoreLabel(score: number): string {
  if (score >= 90) return "Excelente";
  if (score >= 75) return "Bueno";
  if (score >= 60) return "Aceptable";
  if (score >= 40) return "Bajo";
  return "Crítico";
}
