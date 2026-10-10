# Dirección visual de una pantalla

La dirección decide el mundo visual de la pantalla **antes** de escribir código o un prompt.

Se trabaja en dos pasadas:
1. un plan corto;
2. una revisión del plan contra lo que saldría por defecto para «cualquier pantalla parecida».

El proceso condensa el de frontend-design (Anthropic) y el contrato de dirección de Impeccable
(Paul Bakaus). Detalle de fuentes en [../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

> **Condición del owner (UC-9001):** la dirección siempre va seguida de verificación (capturas reales
> y revisión con [rubric.md](rubric.md)). Una dirección ambiciosa sin mirar el resultado es la
> combinación más arriesgada: en la prueba, la dirección sin verificación rompió el móvil de una de las
> dos pantallas; con verificación, quedó en la variante ganadora de las dos.

## Antes de empezar

- **Brief obligatorio.** Lee `doc/design/{feature}/{pantalla}.brief.md`. Sin él no hay dirección.
- **Sistema primero.** Si existen tokens del sistema (`design-system.tokens.json`), un DESIGN.md o un
  brand kit, la dirección **no inventa valores**:
  - colores, tipografías, radios y estados salen del sistema;
  - la dirección decide composición, jerarquía, densidad, qué color del sistema lleva cada
    significado y una pieza propia.
- **Superficie.** Lee la sección de la superficie del brief en [surfaces.md](surfaces.md): en
  Operate, el mundo visual solo presta tipo, paleta, densidad y una pieza propia.

## Pasada 1: el plan

Escríbelo corto, en este orden:

1. **Tema.** Una frase sobre el mundo de la pantalla, sacada del dominio y no de una estética. Por
   ejemplo: «la oficina de carrera durante el fin de semana: el color solo aparece donde alguien
   tiene que actuar».
2. **Paleta (solo sin sistema).** De 4 a 6 colores con nombre, hex y función: fondo, superficie,
   texto, acción y un color por significado (pendiente, error…). Un color, un significado.
3. **Tipografía.** Una o dos familias con su papel y una escala con pasos claros. Cifras con
   `tabular-nums`.
4. **Composición.** Un concepto en una frase y un wireframe ASCII del primer viewport a 1440 px y de
   cómo se reorganiza a 390 px. Indica la alineación.
5. **Pieza propia.** Un solo elemento memorable con sentido en el dominio. Por ejemplo, una parrilla
   donde cada marca es un participante pendiente o verificado. El resto, tranquilo.
6. **Principios.** De 2 a 4 reglas que hacen esta pantalla de este producto y no de otro.

## Pasada 2: revisión contra lo que saldría por defecto

1. Imagina el resultado para un encargo parecido de otro producto. Lo que coincida con tu plan es un
   default, no una decisión.
2. Recorre [defaults.md](defaults.md) y marca cada coincidencia del plan.
3. Para cada una: cámbiala, o escribe por qué el brief o el sistema la justifican. El brief manda
   siempre: si pide una de esas soluciones, se respeta.
4. Anota qué cambiaste y por qué. Es la parte del fichero que más le sirve a quien revise.

## Fichero que se guarda: `{pantalla}.direction.md`

```markdown
# Dirección: {pantalla}

## Tema
## Paleta (o «del sistema: {nombre y versión}»)
## Tipografía
## Composición (wireframe 1440 y 390)
## Pieza propia
## Principios
## Revisión contra lo que saldría por defecto
| Default que aparecía | Qué hice en su lugar | Por qué |
## Lo que se rehúsa en esta pantalla
```

## Para Stitch o Claude Design: el bloque «Visual Direction»

Si la pantalla se genera con Stitch o Claude Design, la dirección va **antes** del prompt de la
pantalla. En la prueba UC-9001, el mismo prompt de Stitch pasó de 5,5 a 12 sobre 40 con este bloque
delante. Sigue siendo un candidato, nunca producción (D18), y se critica con [rubric.md](rubric.md)
antes de guardarlo.

```
Visual Direction (decided before designing; follow it instead of default patterns):
- Concept: {tema en una frase y la pieza propia}.
- Palette: {nombre #hex (función)…} | Use the project's design system (con sistema aplicado).
- Typography: {familias y papel}.
- Layout: {composición por filas o regiones, alineación}.
- Refuse: {los defaults concretos que se rechazaron en la pasada 2}.
```

Con un Design System aplicado en Stitch, quita del bloque los colores, fuentes y radios: los pone
Stitch desde el sistema.
