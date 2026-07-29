# 01 · Product Requirements Document (PRD)

## Resumen ejecutivo

LinkedIn Intelligence es una plataforma web que analiza el mercado laboral tech en tiempo real y genera recomendaciones personalizadas para optimizar perfiles de LinkedIn y CVs. El foco inicial son profesionales que buscan roles en AI Engineering, Analytics Engineering y Data Engineering.

---

## Fases del producto

### Fase 1 — MVP: Analizador de perfil (Mes 1-2)

**Objetivo**: Que el usuario pueda subir su CV o ingresar su URL de LinkedIn y recibir un análisis con recomendaciones concretas.

#### Features

**F1.1 — CV Analyzer**
- El usuario sube un PDF o pega texto de su CV.
- El sistema extrae skills, experiencia, educación y proyectos.
- Calcula un **ATS Score** (0-100) basado en keywords del rol objetivo.
- Lista las keywords presentes, ausentes y su peso relativo.
- Sugiere reformulaciones de bullets con mayor impacto.

Criterios de aceptación:
- [ ] Acepta PDFs de hasta 5MB
- [ ] Extrae texto con >95% de precisión
- [ ] Devuelve análisis en <5 segundos
- [ ] ATS Score correlaciona con resultados reales (validado manualmente)

**F1.2 — LinkedIn Profile Analyzer**
- El usuario ingresa su URL de LinkedIn o pega el texto de su perfil.
- El sistema evalúa: título, about, experiencia, skills, proyectos, educación, certificaciones.
- Devuelve un **Profile Score** (0-100) por sección.
- Lista mejoras ordenadas por impacto.

Criterios de aceptación:
- [ ] Análisis completo de las 6 secciones principales
- [ ] Score por sección + score global
- [ ] Al menos 5 recomendaciones accionables por perfil
- [ ] Tiempo de análisis <10 segundos

**F1.3 — Skills Radar**
- El usuario ingresa el rol objetivo (ej. "AI Engineer").
- El sistema muestra las 50 skills más demandadas en las últimas 4 semanas.
- Clasifica las skills por categoría (lenguajes, frameworks, cloud, soft skills).
- Indica cuáles ya tiene el usuario y cuáles le faltan.

Criterios de aceptación:
- [ ] Datos actualizados con menos de 7 días de antigüedad
- [ ] Mínimo 1.000 ofertas analizadas por rol
- [ ] Skills organizadas en al menos 4 categorías
- [ ] Diferenciación visual entre "tenés" y "te falta"

---

### Fase 2 — Benchmark: Comparación contra los mejores (Mes 3-4)

**F2.1 — Profile Benchmark**
- Compara el perfil del usuario contra los 100 perfiles mejor posicionados para el rol objetivo.
- Muestra percentil del usuario (ej. "tu perfil está en el top 35%").
- Identifica las 3 áreas con mayor brecha.

**F2.2 — Keyword Gap Analysis**
- Analiza las keywords más frecuentes en los mejores perfiles del rol objetivo.
- Indica exactamente qué palabras agregar al título, About, experiencia y skills.
- Ordena por frecuencia de aparición y relevancia semántica.

**F2.3 — Title Optimizer**
- Analiza los 20 formatos de título más efectivos para el rol objetivo.
- Genera 5 variantes de título optimizadas para el perfil del usuario.
- Explica por qué cada variante funciona.

---

### Fase 3 — Generación con IA (Mes 5-6)

**F3.1 — AI About Writer**
- El usuario ingresa su experiencia, skills y objetivo profesional.
- El sistema genera 3 versiones del About optimizadas para el rol objetivo.
- Cada versión tiene un enfoque diferente (técnico, narrativo, orientado a resultados).

**F3.2 — Content Calendar**
- Genera un calendario de 30 días de publicaciones para LinkedIn.
- Cada publicación está orientada a posicionarse en el rol objetivo.
- Incluye formato sugerido (texto, carrusel, video) y hashtags.

**F3.3 — Post Generator**
- El usuario ingresa un tema o proyecto.
- El sistema genera un borrador de publicación optimizado para alcance.
- Sugiere el mejor horario de publicación según el día.

---

### Fase 4 — Job Tracking (Mes 7-8)

**F4.1 — Job Tracker**
- El usuario puede guardar ofertas de trabajo.
- El sistema calcula el fit del perfil con cada oferta (0-100%).
- Muestra exactamente qué falta para alcanzar el 100% de fit.

**F4.2 — Application Optimizer**
- Para cada oferta guardada, genera una versión del CV adaptada.
- Optimiza el cover letter (si aplica).
- Alerta si la oferta tiene requisitos que el perfil no cubre.

**F4.3 — Skills Roadmap**
- Basándose en el gap con las mejores ofertas, genera un roadmap de aprendizaje.
- Prioriza skills por impacto en el rol objetivo.
- Sugiere recursos concretos (cursos, proyectos, certificaciones).

---

### Fase 5 — AI Radar (Mes 9-12)

**F5.1 — Nightly Trend Analysis**
- Cada noche el sistema procesa miles de nuevas ofertas y perfiles.
- Detecta tecnologías que crecieron en las últimas 24/48/72 horas.
- Genera alertas tipo "MCP creció 42% en ofertas de AI Engineer esta semana".

**F5.2 — Market Intelligence Dashboard**
- Panel con tendencias de mercado en tiempo real.
- Comparación de salarios por rol y región.
- Empresas que más están contratando.
- Skills emergentes vs. skills en declive.

**F5.3 — Personalized Alerts**
- El usuario configura alertas para su rol objetivo.
- Recibe notificaciones cuando una skill nueva empieza a aparecer.
- Alertas de nuevas ofertas que coinciden con su perfil en >80%.

---

## Historias de usuario prioritarias

### Como profesional en transición...

**US-001** — Como AI Engineer wannabe, quiero subir mi CV y recibir un ATS Score para saber si mi CV pasa los filtros automáticos de las empresas top.

**US-002** — Como usuario, quiero ver las 50 skills más demandadas para "AI Engineer" esta semana para priorizar qué aprender.

**US-003** — Como usuario, quiero que el sistema analice mi perfil de LinkedIn y me diga exactamente qué cambiar en mi título para aparecer en más búsquedas.

**US-004** — Como usuario, quiero comparar mi perfil con los mejores perfiles de AI Engineer para entender en qué percentil estoy.

**US-005** — Como usuario, quiero que una IA reescriba mi About de LinkedIn usando las keywords correctas y un tono profesional.

**US-006** — Como usuario, quiero recibir alertas cuando una nueva skill técnica empieza a aparecer masivamente en ofertas de mi rol objetivo.

---

## Restricciones y supuestos

### Legales
- No se almacenan datos personales identificables de terceros sin consentimiento.
- Solo se procesan datos públicos de plataformas que lo permiten explícitamente.
- Se respetan los `robots.txt` y `Terms of Service` de cada fuente.
- GDPR/CCPA compliance para usuarios europeos y californianos.

### Técnicas
- El sistema debe funcionar con un presupuesto de infraestructura inicial < USD 100/mes.
- El análisis de CV debe ser stateless (no se almacena el CV del usuario sin opt-in explícito).
- La API debe ser idempotente y documentada con OpenAPI.

### De producto
- MVP funcional en 8 semanas.
- El puntaje ATS debe ser validado manualmente antes del lanzamiento público.
- El primer target son profesionales de Latam (Argentina, México, Colombia, Chile).

---

## Métricas por fase

| Fase | KPI | Target |
|------|-----|--------|
| 1 | CVs analizados / semana | 100 |
| 1 | ATS Score accuracy (vs. manual) | >85% |
| 2 | Profile Benchmark completions | 500 |
| 3 | Abouts generados | 200 |
| 4 | Jobs tracked activos | 50 |
| 5 | Usuarios con alertas activas | 200 |
