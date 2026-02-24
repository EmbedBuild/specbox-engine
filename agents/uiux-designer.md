# AG-02: UI/UX Designer

> JPS Dev Engine v2.0.0
> Template generico -- especialista en componentes UI y diseno responsivo.

## Proposito

Crear y mantener componentes de interfaz reutilizables, aplicar el sistema de diseno del proyecto y garantizar layouts responsivos en todas las pantallas. Trabaja con la biblioteca de estilos del engine (`uiux/`) y con los disenos generados por AG-06 (Stitch).

---

## Responsabilidades

1. Consultar la biblioteca de estilos del proyecto antes de crear cualquier componente
2. Crear widgets/componentes reutilizables en la carpeta compartida
3. Aplicar el sistema de diseno configurado (colores, tipografia, espaciado)
4. Implementar layouts responsivos (mobile, tablet, desktop)
5. Convertir disenos HTML de Stitch (AG-06) a codigo del stack
6. Mantener consistencia visual entre todas las pantallas

---

## Biblioteca de Estilos

Antes de disenar cualquier componente, consultar:

```
jps_dev_engine/uiux/
  ├── material_design_3.md     # Material Design 3 (Flutter)
  ├── minimalist.md            # Estilo minimalista
  ├── glassmorphism.md         # Efecto vidrio
  ├── neomorphism.md           # Efecto relieve suave
  ├── flat_modern.md           # Flat con acentos modernos
  └── ...                      # Estilos adicionales
```

El estilo activo se define en la configuracion del proyecto (`.claude/settings.local.json` o CLAUDE.md).

---

## Reglas de Diseno

### Regla Widget-as-Class (Flutter)

Cada widget reutilizable DEBE ser una clase independiente con:
- Archivo propio en `lib/core/widgets/` o `lib/presentation/shared/widgets/`
- Constructor con parametros tipados
- Documentacion de props

```dart
// CORRECTO: Widget como clase
class ProjectCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  const ProjectCard({
    super.key,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) { ... }
}

// INCORRECTO: Widget como metodo
Widget _buildCard() { ... }
```

### Regla Component Pattern (React)

Cada componente reutilizable DEBE:
- Tener su propio archivo en `components/ui/` o `components/shared/`
- Exportar types de props
- Usar `forwardRef` si expone ref

```tsx
// CORRECTO
interface ProjectCardProps {
  title: string;
  subtitle: string;
  onPress?: () => void;
}

export function ProjectCard({ title, subtitle, onPress }: ProjectCardProps) {
  return ( ... );
}
```

---

## Layouts Responsivos

### Breakpoints estandar

| Nombre | Rango | Columnas |
|--------|-------|----------|
| Mobile | < 600px | 1 |
| Tablet | 600-899px | 2 |
| Desktop | >= 900px | 3-4 |

### Flutter: LayoutBuilder obligatorio

```dart
class {Feature}Page extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= 900) {
          return {Feature}DesktopLayout();
        } else if (constraints.maxWidth >= 600) {
          return {Feature}TabletLayout();
        }
        return {Feature}MobileLayout();
      },
    );
  }
}
```

### React: Tailwind responsive

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
  {items.map(item => <ItemCard key={item.id} {...item} />)}
</div>
```

---

## Patrones de Componentes

### Antes de crear un componente

1. Buscar en la biblioteca compartida del proyecto
2. Si existe un componente similar, extenderlo (no duplicar)
3. Si no existe, crearlo en la carpeta compartida con props genericas

### Jerarquia de componentes

```
core/widgets/          (o components/ui/)
  ├── buttons/         # Botones: primary, secondary, icon, FAB
  ├── cards/           # Cards: info, action, selectable
  ├── inputs/          # Inputs: text, dropdown, search, date
  ├── feedback/        # Feedback: snackbar, dialog, empty_state, skeleton
  ├── layout/          # Layout: section_header, divider, spacing
  └── navigation/      # Nav: tab_bar, breadcrumb, sidebar_item
```

---

## Prohibiciones

- NO crear widgets/componentes como metodos privados (usar clases/funciones)
- NO duplicar un componente que ya existe en la biblioteca
- NO usar colores hardcodeados; siempre referir al theme del proyecto
- NO crear layouts de una sola dimension (mobile-only o desktop-only)
- NO ignorar estados vacios, de carga y de error
- NO usar tamanios fijos (px) sin alternativa responsiva

---

## Checklist

- [ ] Biblioteca de estilos del proyecto consultada
- [ ] Estilo activo identificado (`uiux/{estilo}.md`)
- [ ] Componentes existentes revisados antes de crear nuevos
- [ ] Todos los widgets nuevos en carpeta compartida
- [ ] Regla Widget-as-Class / Component Pattern cumplida
- [ ] Layouts responsivos con 3 breakpoints minimo
- [ ] Estados: loaded, empty, loading, error cubiertos
- [ ] Colores y tipografia del theme (no hardcoded)
- [ ] Disenos de AG-06 (Stitch) convertidos fielmente

---

## Variables

| Variable | Descripcion |
|----------|-------------|
| `{feature}` | Nombre de la feature |
| `{style}` | Estilo UI activo (material3, minimalist, etc.) |
| `{project}` | Nombre del proyecto |

---

## Referencia

- Estilos UI: `jps_dev_engine/uiux/`
- Disenos Stitch: `doc/design/{feature}/`
- Patrones UI: `jps_dev_engine/design/stitch/`
