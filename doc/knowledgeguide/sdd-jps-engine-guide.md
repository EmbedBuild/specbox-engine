# SDD-JPS Engine — Guia para No-Tecnicos

> Documento preparado para Juan Valenzuela
> Fecha: 7 de marzo de 2026
> Version: 3.9.0 "Visual Experience Generation"

---

## Que es el SDD-JPS Engine

Es el **sistema que usamos para construir software**. Piensa en el como una fabrica automatizada: entra un pedido (lo que el cliente quiere) y sale software terminado, testeado y listo para entregar.

**SDD** significa **Spec-Driven Development** (Desarrollo Dirigido por Especificacion). Esto quiere decir que todo parte de un documento firmado con el cliente — no de ideas sueltas ni de conversaciones informales.

El "Engine" es el motor que orquesta todo el proceso: desde que recibimos el pedido hasta que entregamos el producto.

---

## Por que existe

Antes, el proceso de desarrollo dependia mucho de la memoria y criterio individual de cada desarrollador. Esto causaba:

- Funcionalidades que no coincidian con lo que el cliente pidio
- Retrabajos porque se olvidaban requisitos
- Dificultad para demostrar que se entrego lo acordado
- Tiempos de entrega impredecibles

El SDD-JPS Engine resuelve todo esto con **automatizacion y trazabilidad completa**.

---

## Como funciona (en lenguaje simple)

### El flujo completo

```
CLIENTE firma especificacion
        |
        v
  1. REQUISITOS — Se enriquece la especificacion con detalles tecnicos
        |
        v
  2. PLAN — Se genera el plan tecnico de como construirlo
        |
        v
  3. CONSTRUCCION — El sistema construye automaticamente, pieza por pieza
        |
        v
  4. VALIDACION — Se verifica que cada cosa que el cliente pidio esta hecha
        |
        v
  5. ENTREGA — Se entrega con evidencia de que todo cumple
```

### Conceptos clave

| Concepto | Que es | Ejemplo |
|----------|--------|---------|
| **User Story (US)** | Una necesidad del cliente, presupuestable | "Como propietario, quiero gestionar mis inmuebles" |
| **Use Case (UC)** | Una pieza atomica de trabajo dentro de la US | "Crear propiedad con nombre, direccion y foto" |
| **Acceptance Criteria (AC)** | Condicion verificable que debe cumplirse | "Al guardar sin nombre, aparece error rojo" |

**Analogia**: Si la US es "reformar el baño", los UC serian "instalar ducha", "poner azulejos", "conectar fontaneria". Y los AC serian las condiciones de aceptacion: "la ducha no gotea", "los azulejos estan nivelados".

---

## Donde se gestiona todo

### Trello como tablero de control

Usamos **Trello** como el panel de control visible de cada proyecto. Cada proyecto tiene un tablero con 5 columnas:

| Columna | Significado |
|---------|-------------|
| **Backlog** | Trabajo pendiente, aun no priorizado |
| **Ready** | Listo para empezar a construir |
| **In Progress** | En construccion ahora mismo |
| **Review** | Construido, en revision |
| **Done** | Terminado y entregado |

Cada tarjeta en Trello es una US (User Story) o un UC (Use Case). Al abrir una tarjeta puedes ver:

- Las horas estimadas
- Las pantallas afectadas
- Los criterios de aceptacion (AC) con su estado (cumplido o no)
- Los documentos adjuntos (PRD, Plan, Evidencia)

### Evidencia adjunta

El sistema genera y adjunta automaticamente documentos PDF a las tarjetas de Trello:

| Documento | Que contiene | Adjunto en |
|-----------|-------------|------------|
| **PRD** | Requisitos enriquecidos | Tarjeta de la US |
| **Plan** | Plan tecnico de construccion | Tarjeta de la US |
| **Acceptance Report** | Resultado de validacion por UC | Tarjeta del UC |
| **Delivery Report** | Informe final de entrega | Tarjeta de la US |

Esto significa que **en cualquier momento puedes abrir una tarjeta y ver la evidencia de que se cumplio lo acordado**.

---

## Los "agentes" — el equipo automatizado

El engine tiene **11 agentes especializados** que trabajan como un equipo. No son personas — son roles automatizados que hace la inteligencia artificial:

| Agente | Que hace | Equivalente humano |
|--------|----------|-------------------|
| AG-01 | Genera las funcionalidades | Analista de negocio |
| AG-02 | Diseña las pantallas | Diseñador UI/UX |
| AG-03 | Diseña la base de datos | DBA |
| AG-04 | Genera tests de calidad | Tester QA |
| AG-08 | Audita la calidad del codigo | Auditor de calidad |
| AG-09a | Genera tests de aceptacion | Tester de aceptacion |
| AG-09b | Valida que se cumpla la spec | Inspector de entrega |
| AG-10 | Procesa feedback humano | Gestor de incidencias |

El AG-09b es especialmente importante: es el que **verifica que cada criterio de aceptacion firmado con el cliente se ha cumplido**. Si algo no esta bien, bloquea la entrega hasta que se corrija.

---

## Que garantias da el sistema

### 1. Trazabilidad completa

Cada decision, cada linea de codigo, cada test queda registrado. Se puede demostrar en cualquier momento que se hizo lo que se acordo.

### 2. Validacion automatica

No es un humano quien dice "esto esta bien". El sistema verifica automaticamente cada criterio de aceptacion con tests reales y evidencia visual (capturas de pantalla).

### 3. Bloqueo de entrega si no cumple

Si un criterio de aceptacion no se cumple, **el sistema no permite entregar**. No hay forma de "saltarse" la validacion.

### 4. Feedback integrado

Si durante las pruebas manuales alguien encuentra un problema, se registra formalmente y bloquea la entrega hasta que se resuelve.

### 5. Entrega secuencial controlada

Cada pieza (UC) se construye, valida y entrega por separado. No se pasa a la siguiente hasta que la anterior esta completamente validada.

---

## Como afecta a los proyectos

### Para presupuestos

- Cada US tiene horas estimadas visibles en Trello
- Los UC desglosan el trabajo en piezas medibles
- Se puede presupuestar por US (nivel alto) o por UC (nivel detallado)

### Para seguimiento

- El tablero de Trello muestra el estado en tiempo real
- Las columnas (Backlog → Ready → In Progress → Review → Done) dan visibilidad instantanea
- Los documentos adjuntos permiten auditar sin preguntar al equipo tecnico

### Para entregas al cliente

- El Delivery Report es un documento formal que lista cada criterio acordado y su estado
- Las capturas de pantalla demuestran visualmente que funciona
- Si el cliente cuestiona algo, la evidencia esta en la tarjeta de Trello

### Para facturacion

- Una US en columna "Done" con Delivery Report adjunto = trabajo entregable y facturable
- La trazabilidad completa respalda cualquier reclamacion

---

## Stacks soportados (tipos de proyecto)

El engine funciona con varios tipos de tecnologia:

| Tipo | Para que se usa |
|------|----------------|
| **Flutter** | Apps moviles (iOS y Android) |
| **React** | Aplicaciones web |
| **Python** | Backends y APIs |
| **Google Apps Script** | Automatizaciones en Google Workspace |

No necesitas saber que tecnologia usa cada proyecto. Lo relevante es que **el proceso es el mismo independientemente de la tecnologia**: especificacion → plan → construccion → validacion → entrega.

---

## Experiencia visual personalizada (VEG)

Desde la v3.9, el engine genera automaticamente **decisiones visuales adaptadas a la audiencia** del producto. Esto se llama VEG (Visual Experience Generation).

**En lenguaje simple:** cuando el PRD define quien es el publico objetivo (ej: "directivos de empresa" vs "jovenes Gen-Z"), el sistema automaticamente ajusta:

- **Imagenes** — genera ilustraciones y graficos con el tono visual adecuado (corporativo, creativo, juvenil, etc.)
- **Animaciones** — elige el nivel de movimiento en la interfaz (sutil para gobierno, expresivo para consumidor joven)
- **Estilo de diseno** — densidad de informacion, tipografia, colores, espaciado

**Esto es automatico.** Si el PRD tiene seccion de Audiencia, el VEG se activa solo. Si no la tiene, todo funciona como antes.

**Coste:** Las imagenes se generan con Canva (incluido en la suscripcion, €0 adicional). Solo si se necesita fotorrealismo hiperrealista se usa un servicio de pago ($0.02-0.19 por imagen).

---

## Resumen ejecutivo

| Aspecto | Antes | Con SDD-JPS Engine |
|---------|-------|-------------------|
| Origen del trabajo | Conversaciones, emails, ideas sueltas | Especificacion firmada por el cliente |
| Seguimiento | Preguntar al equipo | Tablero Trello en tiempo real |
| Validacion | "Yo creo que esta bien" | Tests automaticos + evidencia visual |
| Entrega | "Ya esta hecho" | Delivery Report con evidencia por criterio |
| Disputas | Palabra contra palabra | Documentacion trazable en cada tarjeta |
| Facturacion | Estimaciones vagas | Horas por US/UC + evidencia de entrega |

---

## Preguntas frecuentes

**P: Necesito instalar algo para ver el estado de un proyecto?**
R: No. Solo necesitas acceso al tablero de Trello del proyecto.

**P: Como se que algo esta realmente terminado?**
R: Cuando la tarjeta esta en la columna "Done" y tiene un Delivery Report adjunto con todos los criterios en PASS.

**P: Que pasa si el cliente dice que algo no funciona?**
R: Se registra como feedback formal (FB-NNN), se bloquea la entrega de esa pieza, y no se desbloquea hasta que se corrija y pase validacion de nuevo.

**P: Puedo ver las capturas de pantalla de lo que se construyo?**
R: Si. Estan adjuntas en la tarjeta del UC correspondiente, dentro del Acceptance Report.

**P: Cuanto tarda el proceso?**
R: Depende del tamano de la US. Pero cada UC (pieza atomica) se construye, valida y entrega individualmente, asi que hay entregas parciales continuas.

---

*SDD-JPS Engine v3.9.0 — Spec-Driven Development Engine by JPS*
