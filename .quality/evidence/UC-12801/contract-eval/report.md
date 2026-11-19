# Contrato antes de las pruebas: la medición (UC-12801 AC-04)

Regla fijada antes de empezar: el contrato gana si, sumando las 5 UC y las dos pasadas, el brazo B (contrato primero) detecta más mutantes que el A (desde los criterios) sin más falsos positivos.

| UC | Brazo | Pasada | Pruebas | Falsos positivos | Mutantes detectados | Tokens | Segundos |
|---|---|---|---|---|---|---|---|
| UC-12305 | A | 1 | 20 | 0 | 10/10 | 176191 | 77.3 |
| UC-12305 | A | 2 | 27 | 0 | 9/10 | 196263 | 148.1 |
| UC-12305 | B | 1 | 39 | 0 | 10/10 | 187917 | 134.3 |
| UC-12305 | B | 2 | 28 | 0 | 10/10 | 198735 | 188.3 |
| UC-12502 | A | 1 | 18 | 0 | 9/10 | 172843 | 73.7 |
| UC-12502 | A | 2 | 26 | 0 | 9/10 | 178272 | 78.5 |
| UC-12502 | B | 1 | 35 | 0 | 10/10 | 190990 | 166.5 |
| UC-12502 | B | 2 | 61 | 0 | 10/10 | 201305 | 165.8 |
| UC-12603 | A | 1 | 39 | 0 | 10/10 | 179068 | 99.9 |
| UC-12603 | A | 2 | 51 | 0 | 9/10 | 179451 | 104.7 |
| UC-12603 | B | 1 | 46 | 0 | 10/10 | 198754 | 201.1 |
| UC-12603 | B | 2 | 67 | 0 | 10/10 | 192628 | 160.2 |
| UC-12604 | A | 1 | 40 | 0 | 8/10 | 193021 | 136.5 |
| UC-12604 | A | 2 | 56 | 0 | 9/10 | 185336 | 110.0 |
| UC-12604 | B | 1 | 46 | 0 | 8/10 | 208617 | 217.4 |
| UC-12604 | B | 2 | 56 | 0 | 8/10 | 222763 | 325.6 |
| UC-12606 | A | 1 | 61 | 0 | 9/10 | 189246 | 103.3 |
| UC-12606 | A | 2 | 81 | 0 | 9/10 | 206970 | 167.3 |
| UC-12606 | B | 1 | 111 | 0 | 9/10 | 213921 | 207.5 |
| UC-12606 | B | 2 | 95 | 0 | 9/10 | 207048 | 199.0 |

**Total A**: 91/100 mutantes detectados, 0 falsos positivos.
**Total B**: 94/100 mutantes detectados, 0 falsos positivos.

**Resultado**: el contrato gana (B detecta más sin más falsos positivos).

## Coste medio por pasada

| Brazo | Pruebas | Tokens del subagente | Segundos |
|---|---|---|---|
| A | 41.9 | 185,666 | 109.9 |
| B | 58.4 | 202,268 | 196.6 |

## Mutantes que no detectó una pasada

| UC | Brazo | Pasada | Mutantes |
|---|---|---|---|
| UC-12305 | A | 2 | M03 |
| UC-12502 | A | 1 | M02 |
| UC-12502 | A | 2 | M02 |
| UC-12603 | A | 2 | M10 |
| UC-12604 | A | 1 | M03, M05 |
| UC-12604 | A | 2 | M04 |
| UC-12604 | B | 1 | M03, M05 |
| UC-12604 | B | 2 | M03, M05 |
| UC-12606 | A | 1 | M06 |
| UC-12606 | A | 2 | M06 |
| UC-12606 | B | 1 | M06 |
| UC-12606 | B | 2 | M06 |

## Límites

- El aislamiento de los subagentes es una instrucción, no una barrera; cada informe lo confirma.
- Los tokens son los del subagente entero (incluye el contexto que recibe al empezar), no solo los de escribir las pruebas.
- Cinco UC del propio engine, de lógica pura en Python; 10 mutantes por UC escritos por agentes aislados (ver `scripts/contract-eval/README.md`).
