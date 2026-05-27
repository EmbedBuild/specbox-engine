# Stitch MCP JSON-RPC Smoke Test — 2026-05-26T23:42:12Z

**Endpoint**: `https://stitch.googleapis.com/mcp`
**Verdict**: `pass`

## Steps

| # | Step | Status | HTTP | Duration |
|---|------|--------|------|----------|
| 1 | `tools/list` | ok | 200 | 581ms |
| 2 | `call list_projects` | ok | 200 | 2147ms |
| 3 | `call create_project` | ok | 200 | 1244ms |
| 4 | `call upload_design_md` | ok | 200 | 3481ms |
| 5 | `call get_project` | ok | 200 | 508ms |
| 6 | `call list_design_systems` | ok | 200 | 1642ms |

## Notes
- Skipped create_design_system_from_design_md: no screen instance

## Raw responses (truncated)
### tools/list
```json
{
  "id": "dcb910b6-5141-4fa1-800e-58fe77d9d12d",
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "annotations": {
          "destructiveHint": true,
          "idempotentHint": false,
          "openWorldHint": false,
          "readOnlyHint": false
        },
        "description": "Creates a new Stitch project. A project is a container for UI designs and frontend code.\n",
        "inputSchema": {
          "description": "Request message for CreateProject.",
          "properties": {
            "title": {
              "description": "Optional. The title of the project.",
              "type": "string"
            }
          },
          "type": "object"
        },
        "name": "create_project",
        "outputSchema": {
          "$defs": {
            "ComponentTokens": {
              "description": "A component style token in a design system.",
              "properties": {
                "tokens": {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "description": "Optional. A component may have these sub tokens: - backgroundColor: - textColor: - typography: - rounded: - padding: The value may be a literal value or a reference. A token reference must be wrapped in curly braces, and contain an object path to another value in the design system. The referenced object must be a primitive value, e.g. colors.primary-60, rather than an object, e.g. colors.",
                  "type": "object"
                }
              },
              "type": "object"
            },
            "DesignTheme": {
              "description": "The theme of the design. Next ID: 27 LINT.IfChange",
              "properties": {
                "backgroundDark": {
                  "deprecated": true,
                  "description": "Optional. DEPRECATED: The background color for dark mode (hex format, e.g., \"#1a1a1a\").",
                  "type": "string"
                },
                "backgroundLight": {
                  "deprecated": true,
                  "description": "Optional. DEPRECATED: The background color for light mode (hex format, e.g., \"#f8f8f8\").",
                  "type": "string"
                },
                "bodyFont": {
                  "description": "Optional. Body font.",
                  "enum": [
                    "FONT_UNSPECIFIED",
                    "BE_VIETNAM_PRO",
                    "EPILOGUE",
                    "INTER",
                    "LEXEND",
                    "MANROPE",
                    "NEWSREADER",
                    "NOTO_SERIF",
                    "PLUS_JAKARTA_SANS",
                    "PUBLIC_SANS",
                    "SPACE_GROTESK",
                    "SPLINE_SANS",
                    "WORK_SANS",
                    "DOMINE",
                    "LIBRE_CASLON_TEXT",
                    "EB_GARAMOND",
                    "LITERATA",
                    "SOURCE_SERIF_FOUR",
              
```

### call list_projects
```json
{
  "id": "5a5b3cb5-183b-4da5-981d-ae4b7683b7b1",
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "{\"projects\":[{\"name\":\"projects/8968909107061645047\",\"visibility\":\"PRIVATE\",\"createTime\":\"2026-05-26T23:39:55.518990Z\",\"updateTime\":\"2026-05-26T23:39:59.075153Z\",\"projectType\":\"TEXT_TO_UI\",\"origin\":\"STITCH\",\"designTheme\":{},\"screenInstances\":[{\"id\":\"12517139344046393767\",\"sourceScreen\":\"projects/8968909107061645047/screens/12517139344046393767\",\"width\":390,\"height\":884}],\"metadata\":{\"userRole\":\"OWNER\"}},{\"name\":\"projects/13334543414981421438\",\"title\":\"Potencial Digital 2026\",\"visibility\":\"PRIVATE\",\"createTime\":\"2026-04-01T19:04:28.058526Z\",\"updateTime\":\"2026-05-26T13:30:33.187241Z\",\"projectType\":\"PROJECT_DESIGN\",\"thumbnailScreenshot\":{\"name\":\"projects/13334543414981421438/files/80fa07d4d0354db9a22c0b72b573e13e\",\"downloadUrl\":\"https://lh3.googleusercontent.com/aida/ADBb0ugdafUfs-Ap2F8HokdkRlMV1XgxQBCJWyQhk0XUAzc30VeibgQyzvMy3WbGHU3Psvuap4cgV1iWdNC2YFcpgnaXAcSX1yDs3Sf2z1PVQMNG27Usthb8WHPh169aBjXTaqSYvGhIpOiOU826krxAg3yghJQvp5thixh-fPHmlRdVIlOdxk-SfSwszRVogH9Nzubxdg0cv5bZr6KzoA37QSMDDpdFbWv_9bvAwaY_VS_VMdsmiFS13OVYTnVM\"},\"origin\":\"STITCH\",\"deviceType\":\"MOBILE\",\"designTheme\":{\"colorMode\":\"DARK\",\"roundness\":\"ROUND_EIGHT\",\"customColor\":\"#1400C5\",\"headlineFont\":\"MONTSERRAT\",\"bodyFont\":\"DM_SANS\",\"labelFont\":\"DM_SANS\",\"designMd\":\"# Potencial Digital 2026 \u2014 Design System\\n\\n## Marca\\n- Claim: \\\"Activa tu potencial\\\" | Hashtag: #PotencialDigital2026\\n- 3er Congreso Extreme\u00f1o de Transformaci\u00f3n Digital, IA y Ciberseguridad\\n- Tono: Educativo, Directo, Atrevido, Digital\\n\\n## Modo visual\\n- Dark mode nativo (fondo #000000 o #121212)\\n- Alta saturaci\u00f3n, colores vibrantes sobre fondo oscuro\\n- Est\u00e9tica tecnol\u00f3gica con toques fl\u00faor\\n\\n## Colores\\n- Primary: #1400C5 (azul el\u00e9ctrico) \u2014 fondos, iconos, brand\\n- Secondary: #FF4A1F (naranja vivo) \u2014 impacto, gradientes, fotograf\u00eda\\n- Tertiary: #09EBE1 (cyan) \u2014 acentos tecnol\u00f3gicos, detalles\\n- Accent/CTA: #E1FF2D (amarillo fl\u00faor) \u2014 botones, highlights, CTAs\\n- Error: #FF2E63 (rosa ne\u00f3n) \u2014 errores, alertas\\n- Surface: #121212 \u2014 cards, modals\\n- On Surface: #FFFFFF \u2014 texto principal\\n\\n## Tipograf\u00eda (en app Flutter se usan las fuentes reales)\\n- Display/Headlines: Lemon (custom, condensada, industrial) \u2192 en Stitch: Montserrat Black/ExtraBold\\n- Body/UI: Darker Grotesque \u2192 en Stitch: DM Sans\\n\\n## Responsive \u2014 3 breakpoints obligatorios\\n- Mobile: \\u003c 600px (1 columna, bottom nav, touch targets 48px)\\n- Tablet: 600-1024px (2 columnas, rail nav, densidad media)\\n- Desktop: \\u003e 1024px (3+ columnas, side nav, densidad alta, hover states)\\n\\n## Componentes clave\\n- Cards con borde sutil (#1E1E1E) sobre fondo #121212\\n- Botones pri
```

### call create_project
```json
{
  "id": "844abeaa-177a-4c1e-8687-f832f6c4cd65",
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "{\"name\":\"projects/7447587180381610792\",\"title\":\"SmokeMCP-1779838934\",\"visibility\":\"PRIVATE\",\"projectType\":\"PROJECT_DESIGN\",\"origin\":\"STITCH\"}",
        "type": "text"
      }
    ],
    "structuredContent": {
      "name": "projects/7447587180381610792",
      "origin": "STITCH",
      "projectType": "PROJECT_DESIGN",
      "title": "SmokeMCP-1779838934",
      "visibility": "PRIVATE"
    }
  }
}
```

### call upload_design_md
```json
{
  "id": "93db901f-d360-4c00-ae0c-f196cbe3aa14",
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "{\"id\":\"11457814419423038419\",\"sourceScreen\":\"projects/7447587180381610792/screens/11457814419423038419\",\"width\":390,\"height\":884}",
        "type": "text"
      }
    ],
    "structuredContent": {
      "height": 884,
      "id": "11457814419423038419",
      "sourceScreen": "projects/7447587180381610792/screens/11457814419423038419",
      "width": 390
    }
  }
}
```

### call get_project
```json
{
  "id": "48005e4b-ea3d-414c-beb8-2db7bf3a3111",
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "Request contains an invalid argument.",
        "type": "text"
      }
    ],
    "isError": true
  }
}
```

### call list_design_systems
```json
{
  "id": "1e77aeb2-c425-4b25-8ddb-78a56b69b9c2",
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "{}",
        "type": "text"
      }
    ],
    "structuredContent": {}
  }
}
```
