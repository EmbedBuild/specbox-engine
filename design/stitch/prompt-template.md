# Plantilla de Prompt para Stitch

## Estructura base
Copiar esta plantilla y rellenar cada seccion segun la pantalla a generar.
```
## Design System
- Theme: Light mode
- Background: #FFFFFF
- Primary color: [color principal del proyecto]
- Secondary color: [color secundario]
- Text primary: #1A1A2E
- Text secondary: #6B7280
- Borders: #E5E7EB
- Font: Inter (or system default sans-serif)
- Border radius: 8px
- Shadows: 0 1px 3px rgba(0,0,0,0.1)

## Screen: [Nombre de la pantalla]
[Descripcion funcional en 2-3 oraciones. Que hace el usuario, objetivo principal,
que informacion se muestra.]

### Components
- [Componente 1]: [descripcion breve]
- [Componente 2]: [descripcion breve]

### States
- Default: [estado inicial al cargar]
- Empty: [estado sin datos, si aplica]

## Layout
- Device: [DESKTOP | MOBILE | TABLET]
- Width: [1440px | 390px | 768px]
- [Indicaciones de distribucion: sidebar, grid, stack vertical, etc.]

## Icons
- Use Material Symbols (Outlined)
- [Listar iconos especificos si son relevantes]
```

**Notas**: Mantener Design System consistente en todo el proyecto. Stitch interpreta mejor descripciones funcionales que listas tecnicas. Ser especifico en componentes: "Tabla con columnas: nombre, email, rol" mejor que "tabla de usuarios". Anchos: 1440px desktop, 390px mobile, 768px tablet.

## Ejemplo: Dashboard principal
```
## Design System
- Theme: Light mode
- Background: #FFFFFF
- Primary color: #2563EB
- Secondary color: #7C3AED
- Text primary: #1A1A2E
- Text secondary: #6B7280
- Borders: #E5E7EB
- Font: Inter (or system default sans-serif)
- Border radius: 8px
- Shadows: 0 1px 3px rgba(0,0,0,0.1)

## Screen: Dashboard Principal
Panel de control principal. Metricas clave en tarjetas superiores, grafica de actividad
de 30 dias en el centro, tabla de transacciones recientes abajo. Sidebar a la izquierda.

### Components
- Sidebar: navegacion vertical con logo, enlaces (Dashboard, Usuarios, Pagos, Ajustes), avatar abajo
- Stat cards: 4 tarjetas con icono, titulo, valor numerico y porcentaje de cambio
- Activity chart: grafica de linea, 30 dias, eje Y numerico, eje X fechas
- Transactions table: columnas (Fecha, Usuario, Concepto, Monto, Estado), 8 filas de ejemplo
- Header: titulo "Dashboard", notificaciones, selector de periodo

### States
- Default: todos los componentes con datos de ejemplo
- Empty: mensaje "No hay datos disponibles" en lugar de grafica y tabla

## Layout
- Device: DESKTOP
- Width: 1440px
- Sidebar fija 260px, contenido principal con padding 32px
- Stat cards en grid de 4 columnas, grafica y tabla apiladas verticalmente

## Icons
- Use Material Symbols (Outlined)
- dashboard, group, payments, settings, notifications, trending_up, trending_down
```
