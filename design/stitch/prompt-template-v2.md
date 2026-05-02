# Stitch Prompt Template v2 (v5.31.0)

> Replaces the legacy minimal template at `design/stitch/prompt-template.md`
> for new generations. v1 stays in place for backwards compat.

Stitch's official prompting guide recommends prompts structured in 4 layers
with explicit boundaries between intents. This template enforces that contract
and is paired with the validator at `server/stitch_prompt/validator.py`, which
runs in `warn` mode by default and can be promoted to `strict` via settings.

## The 4 layers

```
# Layer 1 — CONTEXT (≤80 words)
{screen_purpose} for {audience} on {platform}.
Part of {feature_name} flow. Previous screen: {prev_screen_or_none}.
Next screen: {next_screen_or_none}.

# Layer 2 — COMPONENTS
- {component_1} (state: default | hover | active | error)
- {component_2}
- ...

# Layer 3 — STYLE (hex codes only)
Primary: {hex_from_design_md}
Background: {hex}
Text: {hex}
Spacing: {token_from_design_md}
Typography: {font_family}, sizes {h1_px}/{body_px}
Component patterns: see DESIGN.md > Components

# Layer 4 — PLATFORM
Device: {DESKTOP | MOBILE | TABLET}
Form factor breakpoints: {breakpoint_list}
Interaction model: {touch | mouse | both}
```

## Rules enforced by the validator

1. **Hex codes only.** Named colors (`coral`, `navy`, `blue`) are rejected.
   When a DESIGN.md is present, semantic names that map to palette keys
   (`primary`, `background`, etc.) are auto-resolved to hex.
2. **Layer 1 ≤80 words.** Trim narrative. Stitch doesn't need backstory.
3. **Layer 2 is a bullet list.** Prose components scan worse for the model.
4. **No layout + components in the same call.** A prompt that asks to move
   things AND introduce new elements is split into two sequential calls
   (layout first, components second).
5. **Total length ≤500 chars** (excluding the optional DESIGN.md prefix).

## DESIGN.md prefix

When the project has `doc/design/DESIGN.md` registered against the Stitch
project (via `upload_design_md_to_stitch`), the body is prepended verbatim
fenced as:

```
# DESIGN.md (canonical)
...content...
# End DESIGN.md
```

The validator's length check ignores this fenced block — the prefix can
be large without triggering W1.

## Invocation

Builder: `server.stitch_prompt.builder.build_prompt(layers, design_md_body=...)`
Validator: `server.stitch_prompt.validator.validate_and_normalize(prompt, palette, mode)`
MCP tool: `validate_stitch_prompt(project, prompt, mode='warn'|'strict', project_root=...)`

## Migration

Existing skills that emit free-form prompts continue to work — the v2
validator runs in `warn` mode and never blocks. After 2 weeks of
telemetry collection, the call sites in `/plan` Paso 2.5b can be moved
to use `build_prompt(...)` instead of string concatenation, and the
mode promoted to `strict`.
