# Biblioteca de Estilos UI/UX

Agentes especializados para diferentes estilos visuales en Flutter.

## Estilos Disponibles

| ID | Archivo | Estilo | Mejor para |
|----|---------|--------|------------|
| UIUX-01 | material_design_3.md | Material Design 3 | Apps multiplataforma, Android-first |
| UIUX-02 | cupertino_ios.md | Cupertino/iOS | Apps iOS-first, estética premium |
| UIUX-03 | minimalist.md | Minimalist Modern | Blogs, portfolios, apps de contenido |
| UIUX-04 | neumorphism.md | Neumorphism | Dashboards, controles, apps de nicho |
| UIUX-05 | glassmorphism.md | Glassmorphism | Landing pages, widgets flotantes |
| UIUX-06 | neobrutalism.md | Neobrutalism | Apps creativas, startups, gaming |

## Guía de Selección

¿Qué tipo de aplicación?
│
├─ App empresarial / productividad
│   └─ → Material Design 3
│
├─ App para ecosistema Apple
│   └─ → Cupertino/iOS
│
├─ Blog / portfolio / lectura prolongada
│   └─ → Minimalist Modern
│
├─ Dashboard / controles / smart home
│   └─ → Neumorphism
│
├─ Landing page / marketing / widgets overlay
│   └─ → Glassmorphism
│
└─ App creativa / gaming / startup disruptiva
    └─ → Neobrutalism

## Uso en Proyectos

En el CLAUDE.md del proyecto, especificar:

## Sistema de Diseño
Estilo: Minimalist Modern (UIUX-03)
Ver: ~/.claude-agents/uiux/minimalist.md

## Características Comunes

Todos los estilos incluyen:
- Flutter 3.38.5+ compatible
- Light + Dark mode
- Mobile + Web responsive
- Widgets como clases (prohibido _buildXxx())
- Checklist de revisión
