# Propuestas: landing de acceso anticipado (notas de diseño)

## Concepto
- La idea que lo une todo es el «subrayado»: el amarillo de rotulador marca lo que lee el cliente.
  Aparece en el titular, en la lectura por sección de la maqueta y en la sección más leída de la demostración.
- El gancho es un dolor que reconoce cualquier freelance: «¿Has podido verla?».

## Paleta (modo claro, tokens en :root)
- Papel #F6F3EC y #EEE9DD para alternar bandas; tarjetas #FFFFFF.
- Tinta #16161B; secundaria #3A3941; texto apagado #5C5952 (5,8:1 sobre papel).
- Acento «tinta de firma» #2B3CCB: 7,2:1 sobre papel y 8:1 con texto blanco.
- Marcador #F5D965 / #FBF0BF, solo como fondo para mostrar lectura.
- Verde «aceptada» #1C6A44 sobre #DCEFE3 (5,5:1); error #B42318.
- Borde de los campos #857E70 (3,7:1) para cumplir el contraste de los componentes.

## Tipografía
- Fraunces para los titulares: serif editorial con carácter, y cursiva en los números de paso.
- Hanken Grotesk para el texto (17 px de base), sobria y muy legible.
- IBM Plex Mono para los datos: URL, PIN, fechas, tiempos y etiquetas.

## Layout
- Contenedor de 1200 px con un margen lateral de clamp(16px, 4vw, 40px). Cuadrículas con minmax(0, …).
- Orden: hero, problema (chat), 3 pasos, seguimiento, aceptación, privacidad, comparativa, formulario, preguntas y pie.
- Hero en dos columnas: el texto a la izquierda y, a la derecha, una maqueta CSS del navegador con la propuesta,
  tarjetas flotantes (aperturas, PIN) y el sello «Aceptada».
- A 640 px o menos, las tarjetas flotantes pasan a una fila bajo la maqueta, la tabla se convierte en fichas y
  las filas de lectura apilan la barra.

## Decisiones clave
- Dos demostraciones con poco JS: la lectura por visita (Total, 1.ª y 2.ª) y la aceptación con su recibo y la
  fecha actual en formato es-ES. Un tercer detalle genera un PIN nuevo con un botón de icono que tiene aria-label.
- Una sola historia coherente en toda la página: se envía el lunes 5 de octubre, el miércoles se lee
  Inversión, el viernes 9 se acepta la opción B por 6.450 €. Los datos de la maqueta, del chat y de la cronología cuadran.
- Sin testimonios ni cifras inventadas: la página convence con el producto. No hay marcas de cliente; se usan descripciones como «clínica dental · Valencia».
- La privacidad va a la vista (es lo que dará confianza a los estudios): se enseña el aviso que ve el cliente y se
  dice qué no se mide.
- El formulario valida campo a campo, con errores enlazados por aria-describedby, foco en el primer error,
  estado «Enviando…» y un panel de éxito que recibe el foco. Sin JS, se queda la validación nativa.
- Accesibilidad: enlace para saltar al contenido, foco visible de 3 px, maquetas con role="img" y descripción,
  y prefers-reduced-motion.
