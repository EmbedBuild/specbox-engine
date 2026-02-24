# Integracion Google Stitch MCP

## Que es Stitch

Google Stitch es una herramienta de generacion de interfaces que convierte descripciones textuales en HTML completo y funcional. Se integra con Claude Code a traves del protocolo MCP (Model Context Protocol), permitiendo generar pantallas de UI directamente desde el flujo de desarrollo sin salir del terminal.

Stitch genera HTML estatico con estilos inline que representa fielmente el diseno solicitado. Este HTML sirve como referencia visual y estructural para la conversion posterior a codigo del stack objetivo (Flutter, React, etc.).

## Herramientas MCP disponibles

| Herramienta | Descripcion | Uso tipico |
|-------------|-------------|------------|
| `mcp__stitch__list_projects` | Lista todos los proyectos del usuario | Verificar proyectos existentes |
| `mcp__stitch__get_project` | Obtiene detalles de un proyecto especifico | Consultar configuracion del proyecto |
| `mcp__stitch__list_screens` | Lista las pantallas de un proyecto | Revisar pantallas ya generadas |
| `mcp__stitch__get_screen` | Obtiene el HTML completo de una pantalla | Descargar HTML para conversion a codigo |
| `mcp__stitch__generate_screen_from_text` | Genera una pantalla nueva desde un prompt | Crear disenos de UI |

## Configuracion

Cada proyecto que use Stitch debe tener la configuracion en `.claude/settings.local.json`:

```json
{
  "stitch": {
    "projectId": "ID_DEL_PROYECTO_STITCH",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  }
}
```

**Parametros:**

- `projectId`: ID del proyecto en Stitch. Se obtiene con `mcp__stitch__list_projects`.
- `deviceType`: Tipo de dispositivo objetivo. Valores: `DESKTOP`, `MOBILE`, `TABLET`.
- `modelId`: Modelo de generacion. `GEMINI_3_PRO` para pantallas complejas, `GEMINI_3_FLASH` para pantallas simples.

Si no existe configuracion de Stitch en el proyecto, Claude debe preguntar al usuario antes de proceder.

## Flujo de trabajo

El diseno con Stitch se integra en el flujo estandar del engine:

```
/prd  -->  PRD + tareas en Trello/Plane
  |
/plan  -->  Plan tecnico + disenos Stitch (automatico) + HTML guardados
  |
/design-to-code  -->  HTML de Stitch convertido a codigo Flutter/React/etc
```

### Paso 1: Generacion durante /plan

Cuando se ejecuta `/plan`, Claude identifica las pantallas necesarias y lanza la generacion en Stitch automaticamente. Cada pantalla se genera con un prompt estructurado (ver `prompt-template.md`).

### Paso 2: Almacenamiento de resultados

Los HTML generados se guardan en la estructura del proyecto:

```
doc/design/{feature}/
  {screen_name}.html              # HTML generado por Stitch
  {feature}_stitch_prompts.md     # Registro de prompts utilizados
```

### Paso 3: Conversion a codigo

El comando `/design-to-code` toma los HTML de referencia y los convierte al stack del proyecto, respetando la arquitectura y patrones definidos.

## Reglas de generacion

### Modo visual

**SIEMPRE usar Light Mode.** Todos los prompts deben especificar explicitamente tema claro, fondo blanco y colores apropiados para modo light. No generar pantallas en modo oscuro a menos que el usuario lo solicite explicitamente.

### Seleccion de modelo

- **GEMINI_3_PRO**: Pantallas con multiples componentes, tablas de datos, dashboards, formularios complejos, navegacion anidada. Genera resultados de mayor calidad pero tarda mas.
- **GEMINI_3_FLASH**: Pantallas simples como login, paginas de error, confirmaciones, pantallas con pocos elementos. Mas rapido pero menos detalle.

### Una pantalla a la vez

La API de Stitch tarda varios minutos en generar cada pantalla. Se debe generar una pantalla a la vez y esperar la respuesta antes de lanzar la siguiente. Preguntar al usuario antes de generar cada pantalla adicional.

## Estructura del prompt

Cada prompt enviado a Stitch debe seguir la plantilla definida en `prompt-template.md`. La estructura basica incluye:

1. **Design System**: Tema, colores, tipografia, sombras, bordes.
2. **Pantalla**: Descripcion funcional, componentes requeridos, estados.
3. **Layout**: Dispositivo objetivo, ancho, organizacion espacial.
4. **Iconos**: Familia de iconos a usar (Material Symbols por defecto).

Ver `prompt-template.md` para la plantilla completa y un ejemplo.

## Organizacion de archivos

```
proyecto/
  doc/
    design/
      auth/
        login.html
        register.html
        auth_stitch_prompts.md
      dashboard/
        main_dashboard.html
        analytics.html
        dashboard_stitch_prompts.md
      settings/
        user_profile.html
        settings_stitch_prompts.md
```

El archivo `{feature}_stitch_prompts.md` registra el prompt exacto usado para cada pantalla, facilitando la regeneracion y el ajuste iterativo.

## Estrategia de paralelizacion

La generacion en Stitch es el cuello de botella del flujo (minutos por pantalla). Para optimizar el tiempo total:

1. **Lanzar Stitch primero**: Iniciar la generacion de la pantalla antes de cualquier otra tarea.
2. **Trabajar en paralelo**: Mientras Stitch genera, avanzar con esquemas de base de datos, logica de backend, configuracion de servicios, tests unitarios.
3. **Recoger resultado**: Cuando Stitch termina, guardar el HTML y continuar con la siguiente pantalla o con la conversion a codigo.

Este enfoque reduce significativamente el tiempo muerto y mantiene el flujo de desarrollo continuo.

## Referencia rapida

| Concepto | Valor |
|----------|-------|
| Modo visual | Light Mode (siempre) |
| Modelo complejo | GEMINI_3_PRO |
| Modelo simple | GEMINI_3_FLASH |
| Ruta de HTMLs | `doc/design/{feature}/` |
| Ruta de prompts | `doc/design/{feature}/{feature}_stitch_prompts.md` |
| Generacion | Una pantalla a la vez |
| Iconos por defecto | Material Symbols |
