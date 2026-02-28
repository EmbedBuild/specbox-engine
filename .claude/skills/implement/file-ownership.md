# File Ownership por Agente

Cuando /implement delega fases a sub-tareas, cada tarea solo debe modificar archivos dentro de su ownership:

| Agente/Fase | Ownership (paths permitidos) |
|-------------|----------------------------|
| AG-01 Feature Generator | lib/features/**, src/features/**, app/** |
| AG-02 UI/UX Designer | lib/**/widgets/**, lib/**/screens/**, src/components/**, templates/** |
| AG-03 DB Specialist | lib/**/data/**, supabase/**, prisma/**, migrations/**, sql/** |
| AG-04 QA Validation | test/**, tests/**, __tests__/**, spec/** |
| AG-05 n8n Specialist | n8n/**, workflows/** |
| AG-06 Design Specialist | doc/design/**, design/** |
| AG-07 Apps Script Specialist | src/**, appsscript.json, .clasp.json |
| AG-08 Quality Auditor | .quality/**, doc/plans/** (solo lectura del resto) |
| AG-09a Acceptance Tester | test/acceptance/**, tests/acceptance/**, .quality/evidence/**/acceptance/** |
| AG-09b Acceptance Validator | .quality/evidence/** (solo lectura del resto) |

INSTRUCCION: Al delegar una fase, incluye en el prompt de la sub-tarea:
"Solo modifica archivos dentro de: {ownership_paths}. Si necesitas modificar archivos fuera de tu ownership, repórtalo como dependencia pendiente."
