export interface Contact {
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  linkedin?: string | null;
  github?: string | null;
  website?: string | null;
}

export interface Experience {
  company: string;
  role: string;
  start_date: string;
  end_date: string;
  location?: string | null;
  bullets: string[];
}

export interface Skills {
  languages: string[];
  frameworks: string[];
  cloud: string[];
  databases: string[];
  tools: string[];
  other: string[];
}

export interface Education {
  institution: string;
  degree: string;
  field?: string | null;
  year: string;
  gpa?: string | null;
}

export interface Project {
  name: string;
  description: string;
  technologies: string[];
  url?: string | null;
  highlights: string[];
}

export interface Certification {
  name: string;
  issuer: string;
  year: string;
  url?: string | null;
}

export interface CVData {
  name: string;
  contact: Contact;
  target_role?: string | null;
  summary?: string | null;
  experience: Experience[];
  skills: Skills;
  education: Education[];
  projects: Project[];
  certifications: Certification[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  id?: string;
}

export interface SSEEvent {
  type: "text" | "cv_update" | "done";
  content?: string;
  section?: string;
  index?: number;
  field?: string;
}
