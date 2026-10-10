# Rúbrica de revisión ciega (0-5 por criterio; 5 = excelente)

1. **Especificidad**: ¿la pantalla está pensada para ESTE producto (propuestas a pymes, un usuario, Jerez) o serviría igual para cualquier SaaS? ¿El contenido y la copy son del producto?
2. **Jerarquía y escaneabilidad (Operate)**: ¿responde en segundos a «quién abrió qué», «qué sección frena», «a quién llamo hoy»? ¿La densidad es la adecuada para una herramienta diaria?
3. **Tells de IA**: contar y listar los que aparezcan: eyebrows en mayúsculas con tracking, tarjetas idénticas anidadas, hero-metric genérico (número grande + etiqueta), gradiente morado/azul, gradient text, glass decorativo, borde lateral de color >1px, sombra gris uniforme en todo, Inter/Roboto/Arial/Space Grotesk como única voz, crema+terracota o negro+verde ácido por defecto, `→` en botones, puntos medios « · » encadenados, numeración 01/02/03 sin secuencia, lorem/Acme, emojis como iconos. Puntuar 5 = ninguno, 0 = cinco o más.
4. **Tipografía**: elección deliberada y con carácter, escala clara, medida de línea, tabular-nums en cifras, sin all-caps innecesario.
5. **Color**: paleta comprometida y coherente, un acento con función (acción/selección/estado), neutros entonados (no gris puro), contraste AA en cuerpo y placeholders.
6. **Estados y craft**: estado vacío que enseña, skeleton (no spinner), error inline con recuperación, hover/focus/active/disabled definidos, foco visible, áreas de pulsación ≥40px, radios concéntricos, sombras con offset y blur.
7. **Responsive**: a 390 px sin scroll horizontal, tabla/lista reconvertida con sentido, navegación usable.
8. **Movimiento**: solo transform/opacity, duraciones ≤300ms, ease-out en entradas, nada de `transition: all`, respeto a prefers-reduced-motion, sin animaciones decorativas en carga.

Entrega por variante: tabla con las 8 puntuaciones, total sobre 40, lista de tells encontrados (criterio 3) con la línea del HTML donde aparecen, 2 fortalezas, 3 problemas prioritarios. Al final, ranking y una línea de veredicto por variante.
