# Brief P1: «Participantes de la prueba» (pantalla de app, modo Operate)

## Producto y contexto real

PaddockManager es la plataforma con la que la Real Federación Motociclista Española (RFME) gestiona el
Campeonato de España de Superbike (ESBK). Tiene una web de gestión y una app móvil para el paddock.

La inscripción y el pago no pasan por PaddockManager: los gestiona el sistema de la RFME. Antes de cada
prueba, el organizador **importa el Excel oficial de inscritos** y, a partir de ahí, cada inscrito es un
**participante** con:

- dorsal, categoría, moto, equipo, box y licencia;
- dos verificaciones que hacen los comisarios técnicos durante el fin de semana: **moto** y **equipo**.
  Cada una tiene la fecha en que se hizo o está pendiente.

La importación descarta las filas incompletas (sin licencia, sin categoría o con dorsal no numérico),
las duplicadas y las que traen una categoría que no existe en el campeonato.

## Quién la usa y para qué

La usa el **director técnico u organizador de la prueba**, varias veces al día durante el fin de semana
de carrera. Suele estar en un portátil en la oficina de carrera (1440 px) y a veces mira el móvil en el
paddock (390 px).

Tiene que responder en segundos a tres preguntas:

1. **¿Quién falta por pasar la verificación de moto o de equipo, y en qué box está?**
2. **¿Quién tiene algo que resolver en oficina antes de salir a pista?** Por ejemplo: licencia
   provisional o extranjera, sin pegatina en la moto, casco sin QR FIM o una fila del Excel que no entró.
3. **¿Cómo va cada categoría?** Verificados frente a pendientes.

No es una landing: es una herramienta de trabajo durante la carrera.

## Pantalla a construir (una sola página HTML)

1. **Cabecera** con la prueba (ESBK 2026 · Navarra I · Circuito de Navarra, Los Arcos · 8 y 9 de
   mayo), buscador por piloto, dorsal o equipo, y las acciones «Importar Excel RFME», «Añadir
   participante» e «Imprimir PDF».
2. **Estado de la verificación por categoría**: 129 participantes, de los que 104 están verificados
   (81 %). Desglose:

   | Categoría | Participantes | Pendientes |
   |---|---|---|
   | Yamaha R7 Cup | 29 | 6 |
   | ESBK Talent | 25 | 4 |
   | PreTalent | 14 | 3 |
   | Supersport 300 | 14 | 3 |
   | Sportbike | 13 | 3 |
   | Superstock 1000 | 11 | 2 |
   | Superstock 600 | 10 | 2 |
   | Supersport | 9 | 1 |
   | Superbike | 4 | 1 |
3. **Lista de participantes**: hay 129, así que hay que mostrarlos con búsqueda, filtro por categoría y
   por pendiente y orden por dorsal. Se ven al menos las 8 filas de ejemplo, con dorsal, piloto,
   categoría, moto, equipo, box, licencia y el estado de verificación de moto y de equipo.
4. **Panel de detalle** del participante seleccionado, con:
   - dorsal, categoría, moto, equipo, box, licencia y país;
   - verificación de moto y de equipo, con fecha y hora o pendiente;
   - cascos (pegatina y QR FIM);
   - avisos de oficina;
   - acciones «Editar participante» y «Asignar box».
5. **Filas del Excel que no entraron**: 3 de 132, cada una con su motivo.
6. **Estados**: lista vacía (ningún participante coincide con la búsqueda o el filtro), carga (skeleton)
   y un error inline (por ejemplo, fallo al importar el Excel). Pueden ir como variantes visibles al pie
   o en un bloque de demostración.

## Datos reales de ejemplo

Nombres de piloto y equipo **inventados**. Campeonato, circuito y categorías, reales. Hoy es el
**viernes 8 de mayo de 2026, 09:40**.

**Participantes importados:**

| Dorsal | Piloto | País | Categoría | Moto | Equipo | Box | Moto verificada | Equipo verificado | Avisos |
|---|---|---|---|---|---|---|---|---|---|
| 7 | Iker Valdemoro Sanz | ESP | Superbike | Honda CBR1000RR-R | Valdemoro Racing | 12 | 8 may 08:15 | 8 may 08:20 | — |
| 39 | Bruno Lavín Ortuño | ESP | Superstock 1000 | BMW M1000RR | Team Ortuño SBK | 21 | pendiente | 8 may 08:42 | Corría en Superbike la prueba anterior |
| 21 | Pau Ferrandis Llobet | ESP | Sportbike | Kawasaki Ninja 400 | Llobet Motorsport | 14 | 8 may 09:05 | pendiente | Licencia provisional: falta la de su federación autonómica |
| 21 | Hugo Cebrián Montaner | ESP | Yamaha R7 Cup (Rookie) | Yamaha R7 | Montaner Junior Team | Carpas Yamaha R7 | pendiente | pendiente | Moto sin pegatina; el dorsal 21 también está en Sportbike (es válido) |
| 15 | Lucía Arranz Peñalver | ESP | ESBK Talent | Honda NSF250R | Arranz Academy | 25 | 8 may 08:31 | 8 may 08:35 | Menor de edad (14 años) |
| 8 | Mateo Rubial Gaspar | ESP | PreTalent | Beon (sin modelo) | — | Carpas Paddock | 8 may 09:12 | pendiente | Sin equipo; casco sin QR FIM |
| 67 | Théo Marchandeau | FRA | Superstock 600 | Yamaha R6 | Équipe Lumière | 3 | 8 may 08:58 | pendiente | Licencia de la federación francesa (FFM) |
| 44 | Nerea Olmedilla Ruiz | ESP | Supersport 300 | «SIN MARCA» en el Excel | Olmedilla Racing | 18 | pendiente | 8 may 09:30 | Marca y modelo de la moto por completar |

**Filas del Excel que no entraron** (3 de 132):

- Fila 46, Daniel Escartín Moreno (dorsal 52, «Supersport NG»): la categoría no existe en el campeonato,
  porque usa el nombre antiguo.
- Fila 88, Álvaro Cifuentes Rey (dorsal 33, Superstock 600): falta la licencia.
- Fila 131, Iker Valdemoro Sanz (dorsal 7, Superbike): fila duplicada.

## Restricciones técnicas

- Un único fichero HTML autocontenido, con el CSS dentro de `<style>`. JavaScript mínimo y opcional,
  solo para demostrar estados. Sin frameworks ni Tailwind. Se permite Google Fonts mediante `<link>`.
- **Modo claro**. Idioma: español de España. Fechas y horas en formato español.
- Tiene que funcionar a 1440 px y a 390 px sin scroll horizontal.
- Accesibilidad básica: contraste AA, foco visible y etiquetas en los botones de icono.
- Nada de texto de relleno (lorem ipsum) ni marcas inventadas tipo «Acme».
- **El HTML no puede incluir ningún comentario ni texto que mencione qué skill o guía se ha usado.**
