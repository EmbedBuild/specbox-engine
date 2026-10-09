# Brief P2: landing de «Propuestas» (página comercial, modo Persuade)

## Producto y contexto real

embed.build es un estudio de software unipersonal de Jerez de la Frontera. Envía sus propuestas
comerciales como una página web privada con enlace y PIN, en lugar de un PDF adjunto.

La herramienta que usa para hacerlo se llama **Propuestas** y vive en `propuestas.embed.build`. Lo que
hace hoy, sin inventar nada:

- Cada propuesta es una página web con secciones (Resumen, Alcance, Inversión, Plazos, Condiciones) y un
  PDF con el mismo contenido.
- El cliente la abre con un enlace y un PIN de 4 cifras. El PIN se le manda por otro canal (WhatsApp o
  teléfono). El cliente no crea ninguna cuenta.
- Quien la envía ve:
  - las aperturas, con fecha, hora y dispositivo (portátil o móvil);
  - el tiempo de lectura de cada sección, que le dice dónde se frenó el cliente;
  - si la propuesta se ha aceptado online.
- Puede ampliar la validez, generar un PIN nuevo o revocar el acceso.
- Opcionalmente, la propuesta puede llevar una calculadora de retorno que el cliente toca.

La página que hay que diseñar es la **landing pública de Propuestas**: la que presenta la herramienta a
otros estudios pequeños y freelancers y les invita a pedir **acceso anticipado**. El producto todavía
no está abierto a terceros: no hay precios ni clientes externos.

## Quién la visita y para qué

Un freelancer o un estudio de 1 a 5 personas (diseño, desarrollo, marketing) que vende proyectos a
pymes. Hoy manda propuestas en PDF por email y no sabe si se leen. Llega desde LinkedIn o por
recomendación, y la mitad de las veces desde el móvil (390 px); el resto, en portátil (1440 px).

Tiene que poder responder en menos de un minuto:

1. ¿Qué gano frente a mandar un PDF?
2. ¿Qué ve mi cliente y qué tiene que hacer? (Sin cuenta: enlace y PIN.)
3. ¿Cómo empiezo y qué me cuesta? (Acceso anticipado gratuito; los precios no están decididos.)

## Página a construir (un único HTML)

1. **Cabecera** con el nombre del producto y el acceso a «Pedir acceso anticipado».
2. **Primera pantalla** con la propuesta de valor y la llamada a la acción principal.
3. **Cómo funciona**, en tres pasos: preparas la propuesta, la envías con enlace y PIN, y ves qué se lee
   y cuándo se acepta.
4. **Lo que ves tú**: una representación del panel de seguimiento (aperturas, lectura por sección,
   aceptación), hecha con HTML, CSS o SVG. Nada de capturas inventadas como imagen.
5. **Lo que ve tu cliente**: la propuesta en el móvil, sin registro, con el PIN.
6. **Preguntas frecuentes**, cuatro como mínimo:
   - ¿Mi cliente necesita cuenta?
   - ¿Puedo usar mi marca?
   - ¿Dónde están los datos y qué pasa con el RGPD? (La respuesta concreta va como marcador
     `[DATO REAL]`, porque aún no está publicada.)
   - ¿Cuánto cuesta?
7. **Formulario de acceso anticipado** con nombre, email y a qué te dedicas, con sus estados: enviado,
   error de email no válido y error de envío con reintento. Pueden ir como variantes visibles al pie
   o en un bloque de demostración.

## Datos de ejemplo (usar estos, no inventar «Acme»)

Para la representación del panel, usar como ejemplo una propuesta a «Taller Hermanos Ríos» («Web de
citas para el taller», 4.800 €): abierta 3 veces, 9 min de lectura, se frenó 4 min 35 s en Inversión.

Cualquier cifra de resultados que no venga de aquí va como marcador entre corchetes, por ejemplo
`[CIFRA REAL]`. Nada de testimonios ni logos de clientes inventados.

## Restricciones técnicas

- Un único fichero HTML autocontenido, con el CSS dentro de `<style>`. JavaScript mínimo y opcional,
  solo para los estados del formulario y demostraciones. Sin frameworks ni Tailwind. Se permite Google
  Fonts mediante `<link>`.
- **Modo claro**. Idioma: español de España. Moneda en euros y fechas en formato español.
- Tiene que funcionar a 1440 px y a 390 px sin scroll horizontal.
- Accesibilidad básica: contraste AA, foco visible, etiquetas en los botones de icono y en los campos.
- Sin imágenes externas ni fotos de stock: ilustraciones y maquetas en HTML, CSS o SVG.
- Nada de texto de relleno (lorem ipsum) ni marcas inventadas tipo «Acme».
- **El HTML no puede incluir ningún comentario ni texto que mencione qué skill o guía se ha usado.**
