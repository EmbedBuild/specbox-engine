# Stitch MCP JSON-RPC Smoke Test v2 — 2026-05-26T23:44:02Z

**Endpoint**: `https://stitch.googleapis.com/mcp`
**Verdict**: `pass`
**Screen instance found**: True
**Asset ID resolved**: `dff528fbb925415d9582bd8a04dd729f`

## Steps

| # | Step | Status | HTTP | Duration | Notes |
|---|------|--------|------|----------|-------|
| 1 | `create_project` | ok | 200 | 1097ms | keys=['name', 'title', 'visibility', 'projectType', 'origin'] |
| 2 | `upload_design_md` | ok | 200 | 4198ms | keys=['id', 'sourceScreen', 'width', 'height'] |
| 3 | `get_project_by_name` | ok | 200 | 921ms | keys=['name', 'title', 'visibility', 'createTime', 'updateTime', 'projectType'] |
| 4 | `list_design_systems_pre` | ok | 200 | 1493ms | keys=[] |
| 5 | `create_design_system_from_design_md` | ok | 200 | 43516ms | keys=['assetId'] |
| 6 | `list_design_systems_post` | ok | 200 | 1977ms | keys=['designSystems'] |
| 7 | `update_design_system` | ok | 200 | 6258ms | keys=['name', 'designSystem'] |
| 8 | `apply_design_system` | ok | 200 | 19072ms | keys=['projectId', 'sessionId', 'outputComponents'] |

## Parsed responses (truncated)
### create_project
```json
{
  "name": "projects/9887632132611822982",
  "title": "SmokeMCPv2-1779839042",
  "visibility": "PRIVATE",
  "projectType": "PROJECT_DESIGN",
  "origin": "STITCH"
}
```

### upload_design_md
```json
{
  "id": "7723562061268561647",
  "sourceScreen": "projects/9887632132611822982/screens/7723562061268561647",
  "width": 390,
  "height": 884
}
```

### get_project_by_name
```json
{
  "name": "projects/9887632132611822982",
  "title": "SmokeMCPv2-1779839042",
  "visibility": "PRIVATE",
  "createTime": "2026-05-26T23:44:03.019026Z",
  "updateTime": "2026-05-26T23:44:06.532407Z",
  "projectType": "PROJECT_DESIGN",
  "origin": "STITCH",
  "designTheme": {},
  "screenInstances": [
    {
      "id": "7723562061268561647",
      "sourceScreen": "projects/9887632132611822982/screens/7723562061268561647",
      "width": 390,
      "height": 884
    }
  ],
  "metadata": {
    "userRole": "OWNER"
  }
}
```

### list_design_systems_pre
```json
{}
```

### create_design_system_from_design_md
```json
{
  "assetId": "dff528fbb925415d9582bd8a04dd729f"
}
```

### list_design_systems_post
```json
{
  "designSystems": [
    {
      "name": "assets/dff528fbb925415d9582bd8a04dd729f",
      "designSystem": {
        "displayName": "SmokeTest M3 Tokens",
        "styleGuidelines": "## Brand & Style\nThis design system is built for technical environments where clarity, speed, and reliability are paramount. It adopts a **Corporate / Modern** aesthetic with strong influences from Material 3 principles, prioritizing a functional and utilitarian interface. The brand personality is systematic and unobtrusive, designed to support complex workflows without visual fatigue. The visual language utilizes high-contrast text and a structured color application to ensure the user\u2019s focus remains on data and status indicators.\n\n## Layout & Spacing\nThe layout relies on a **Fluid Grid** system with a base 8px spacing rhythm (4px increments for fine-tuning). \n\nOn desktop, a 12-column grid is used with 16px gutters and 32px side margins. On mobile, the system collapses to a 4-column grid with 16px side margins. Spacing between related elements (like labels and inputs) should use `space-sm`, while spacing between distinct sections should use `space-lg` or `space-xl`.\n\n## Elevation & Depth\nVisual hierarchy is established through **Tonal Layers** and **Ambient Shadows**. Surfaces are tiered to represent depth:\n- **Level 0 (Background):** Solid `#FFFFFF`.\n- **Level 1 (Cards/Sheet):** Slight ambient shadow (0px 2px 4px, 5% opacity) or a 1px `outline` border.\n- **Level 2 (Modals/Popovers):** Higher diffusion shadow (0px 8px 16px, 10% opacity).\n\nInstead of heavy shadows, the system prefers using the `primary-container` and `outline` colors to create structural definition and depth.\n\n## Components\n- **Buttons:** Primary buttons use a solid `primary` background with `on-primary` text. Secondary buttons use the `outline` for a ghost-style appearance or the `primary-container` for a tonal, low-priority look.\n- **Chips:** Used for filtering and status; they should use the `primary-container` for active states and a light neutral background for inactive ones.\n- **Input Fields:** Use the `outline` color for the border in the default state, thickening and changing to `primary` on focus. Labels should be `label-md` and placed above the field.\n- **Cards:** White surfaces with a 1px `outline` border and a `rounded-lg` radius.\n- **Lists:** Clean rows with `space-md` vertical padding and a subtle `outline` divider between items.\n- **Checkboxes & Radio Buttons:** When 
```

### update_design_system
```json
{
  "name": "projects/9887632132611822982/sessions/13768570501260803832",
  "designSystem": {
    "displayName": "SmokeTest Update",
    "theme": {
      "colorMode": "LIGHT",
      "roundness": "ROUND_EIGHT",
      "customColor": "#0EA5E9",
      "headlineFont": "INTER",
      "bodyFont": "INTER"
    }
  }
}
```

### apply_design_system
```json
{
  "projectId": "9887632132611822982",
  "sessionId": "1653082140869513894",
  "outputComponents": [
    {
      "design": {
        "screens": [
          {
            "screenshot": {
              "name": "projects/9887632132611822982/files/2eb7985a2b1d4b7b82ebf8d642b36677",
              "downloadUrl": "https://lh3.googleusercontent.com/aida/ADBb0uhenAYmgnwLzDSn3FoQVs0VZlJTDbCAHp6dI-YbkzfMzqsuTQJ37Ww3N-VpmBwLAq1tDIU2doPcnlKdWdkA2H9TK3eGQa5RSKxKKXhWKnkN5sIDLMEwVNberzvCfUbdyvgOfdNCaIk0io6pS01orCfGLzXGZNhPW0-pJghVZVcOjVWBoUhF4AZUU-10umZoAP_aqllrtsTPASX1EnlLrWQ41PYV1vqjyN19vXorhd-3tzuBRZMA-gb6CGI"
            },
            "htmlCode": {
              "name": "projects/9887632132611822982/files/93611b63068246718da75815433e9893",
              "downloadUrl": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzU4NjE5ZDhlZWVjMDQyN2E4MDE3OWYxNWNhZjU1ZDY5EgsSBxD99oOQ-gQYAZIBIwoKcHJvamVjdF9pZBIVQhM5ODg3NjMyMTMyNjExODIyOTgy&filename=&opi=96797242",
              "mimeType": "text/html"
            },
            "id": "6f20f57fbb8c4aa383615643b2901191",
            "generatedBy": "polish_edit_theme_agent",
            "width": "2560",
            "height": "2048",
            "title": "DESIGN.md",
            "name": "projects/9887632132611822982/screens/6f20f57fbb8c4aa383615643b2901191",
            "theme": {
              "colorMode": "LIGHT",
              "font": "INTER",
              "roundness": "ROUND_EIGHT",
              "customColor": "#0ea5e9",
              "headlineFont": "INTER",
              "bodyFont": "INTER",
              "labelFont": "INTER",
              "namedColors": {
                "background": "#f6faff",
                "error": "#DC2626",
                "error_container": "#ffdad6",
                "inverse_on_surface": "#edf1f7",
                "inverse_primary": "#89ceff",
                "inverse_surface": "#2c3135",
                "on-primary-container": "#0C4A6E",
                "on-surface": "#1A1A1A",
                "on_background": "#171c20",
                "on_error": "#ffffff",
                "on_error_container": "#93000a",
                "on_primary": "#ffffff",
                "on_primary_container": "#003751",
                "on_primary_fixed": "#001e2f",
                "on_primary_fixed_variant": "#004c6e",
                "on_secondary": "#ffffff",
                "on_secondary_container": "#54647a",
                "on_seconda
```
