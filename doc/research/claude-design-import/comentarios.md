# Los comentarios del lienzo se vuelven correcciones o feedback (UC-9203)

> Fecha: 2026-10-10 · Claude Code 2.1.288 · lienzo de prueba de UC-9201: la cola de aceptación y el
> detalle de una UC, con el sistema «Tinta prueba».

El owner dejó dos comentarios en el lienzo, cada uno anclado a un artboard y enviado a Claude:

| Hilo | Artboard | Comentario | Tipo | Qué se hizo |
|---|---|---|---|---|
| 1 | `Main.dc.html` (cola, 1440) | «En "cargando" pone 0 pendientes y parece que no hay nada» | diseño | Corrección propuesta y confirmada. Solo se tocó ese artboard (versión 7 del lienzo): el recuento de la cabecera ya no sale mientras carga (hueco de esqueleto) ni con error, y el 0 solo con la cola vacía. Comprobado en la copia congelada con `--states`. Respuesta en el hilo con lo que cambió y hilo resuelto |
| 2 | `detalle.dc.html` (detalle, 1440) | «Quiero poder rechazar la UC con un motivo, no solo pedir cambios» | alcance | Ningún criterio recoge un rechazo: el AC-01 de UC-7604 (aceptación humana en el panel) define aceptar, «Aceptada por X · fecha» y retirar. Clasificado como alcance y confirmado. **El lienzo no se tocó** (sigue en la versión 7). Feedback FB-001 (minor, no invalida la aceptación) con los pasos de `/feedback` y `report_feedback`. Respuesta en el hilo y hilo resuelto |

Los dos quedaron apuntados en `claude-design.json` (`comentarios`) con `canvas.mjs comment-record`, y
una segunda pasada ya no los propone.

## Hallazgo: la respuesta automática se adelanta

La sesión que crea un lienzo queda suscrita a él con las respuestas automáticas activas. En los dos
hilos contestó sola en segundos, antes de cualquier clasificación:
- en el primero, «Me pongo con ello»;
- en el segundo, «estoy añadiendo una acción Rechazar». Prometía dibujar un cambio de alcance.

Ninguna de las dos tocó el lienzo; lo comprobamos por la versión. La respuesta de `/design-review
comments` corrigió la segunda: «no he añadido Rechazar; es alcance; registrado como FB-001». La
referencia lo explica (paso 7). Cada respuesta nueva usa `acknowledge_duplicate: true` porque añade lo
que se hizo.
