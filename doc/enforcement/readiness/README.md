# Prueba antes de que una medida nazca en «block» (UC-12213)

Las medidas de EP-20 nacen en «warn», también en los proyectos nuevos. Una medida solo pasa a «block»
por defecto en los proyectos nuevos (`new_default="block"` en `server/coordination/enforcement.py`)
si en los tableros de EmbedBuild:

- lleva **14 días seguidos** bloqueando (el primer bloqueo es de hace 14 días o más);
- tiene **al menos 20 bloqueos** en los últimos 14 días (con menos no hay dato);
- sus **saltos** con motivo son el **10 % o menos** de esos bloqueos.

Un salto con motivo es la señal de que la medida se equivocó: si la gente la salta mucho, no está lista.

## Cómo se hace el cambio

1. El operador ejecuta `enforcement_readiness` (solo operador) y guarda la respuesta de la medida en
   `doc/enforcement/readiness/<clave>.json`, con la fecha:

   ```json
   {"measure": "spec_quality", "checked_at": "2027-01-15T10:00:00+00:00",
    "blocks": 34, "skips": 2, "skip_rate": 0.0588, "first_block_at": "2026-12-20T09:12:00+00:00",
    "candidate": true}
   ```

2. Una versión del engine, con su codename aprobado por Jesús, cambia `new_default` a «block» y lleva
   en su CHANGELOG la sección «Para los proyectos que ya existían» (`/release`, Paso 5.5.4).

`tests/test_enforcement.py` falla si una medida tiene `new_default="block"` sin ese fichero o con un
fichero que no cumple la regla. La tool nunca cambia el valor por defecto: solo lo lee.

Los proyectos que ya existían no cambian con esto: siguen en «warn» hasta que quien administra el
proyecto pase la medida a «block» con `set_enforcement_mode`, que primero enseña el informe de impacto.
