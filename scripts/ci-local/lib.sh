#!/usr/bin/env bash
# ci-local · librería común del CI local (estándar v1)
#
# Se copia en cada repo como scripts/ci-local/lib.sh y la carga scripts/ci-local.sh:
#
#   . "$ROOT/scripts/ci-local/lib.sh"
#   CI_NOMBRE="API"; CI_BLOQUES="secretos gates"; CI_DOCKER="gates"
#   secretos() { ci_secretos; }
#   gates()    { ci_paso "Dependencias" pnpm install && ci_paso "Pruebas" pnpm test; }
#   ci_abrir "$@"
#   ci_correr secretos & ci_correr gates
#   ci_cerrar
#
# Ejecutada directamente:  lib.sh estado [carpeta|--todos]  ·  lib.sh contar <registro>  ·  lib.sh version
#
# El estándar completo está en la skill ci-local (references/estandar.md). No se edita en el repo del proyecto:
# se pone al día con «ci_local.py actualizar». Compatible con Bash 3.2 (macOS) y Bash 5 (Linux).

CI_LIB_VERSION="1.2.1"
CI_ESTANDAR=1

# --- Utilidades ------------------------------------------------------------------------------------------------------

_ci_error() { printf '[ci-local] ERROR: %s\n' "$*" >&2; }

# Carpeta común de todas las ejecuciones: $TMPDIR/ci-local (o CI_LOCAL_BASE).
_ci_base() {
  local t="${TMPDIR:-/tmp}"
  t="${t%/}"
  printf '%s\n' "${CI_LOCAL_BASE:-$t/ci-local}"
}

# _ci_escribir <fichero> <etiqueta> <línea…>: escritura atómica (temporal + mv). Cada escritor usa su etiqueta.
_ci_escribir() {
  local f="$1" tag="$2"
  shift 2
  printf '%s\n' "$@" >"$f.tmp-$tag" && mv -f "$f.tmp-$tag" "$f"
}

_ci_en() {
  local x="$1" y
  shift
  for y in "$@"; do [ "$x" = "$y" ] && return 0; done
  return 1
}

_ci_vivo() { [ -n "${1:-}" ] && ps -p "$1" >/dev/null 2>&1; }

# Valor de una variable por nombre (CI_LIMITE_<bloque>, CI_PASOS_<bloque>); los guiones del bloque pasan a «_».
_ci_var() {
  local n="$1"
  n="${n//-/_}"
  printf '%s' "${!n:-}"
}

_ci_tiempo() {
  local s="${1:-0}"
  if [ "$s" -ge 60 ] 2>/dev/null; then printf '%dm%02ds' $((s / 60)) $((s % 60)); else printf '%ss' "$s"; fi
}

_ci_hora() { date -r "$1" '+%H:%M' 2>/dev/null || date -d "@$1" '+%H:%M' 2>/dev/null || echo "?"; }

_ci_descendientes() {
  local h
  for h in $(pgrep -P "$1" 2>/dev/null); do
    _ci_descendientes "$h"
    echo "$h"
  done
}

# Mata un proceso y todos sus descendientes (TERM; con --duro, KILL a los 2 s a quien siga vivo).
_ci_matar_arbol() {
  local pids
  pids="$(_ci_descendientes "$1") $1"
  # shellcheck disable=SC2086
  kill -TERM $pids 2>/dev/null
  if [ "${2:-}" = --duro ]; then
    sleep 2
    # shellcheck disable=SC2086
    kill -KILL $pids 2>/dev/null
  fi
  return 0
}

_ci_json_str() {
  local s="$1"
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  printf '"%s"' "$s"
}

_ci_json_lista() {
  local out="" x
  for x in "$@"; do out="$out${out:+, }\"$x\""; done
  printf '[%s]' "$out"
}

# _ci_campo <inicio.json> <clave>: valor de una clave (texto, número o lista en una línea).
_ci_campo() {
  local v
  v="$(sed -n "s/^  \"$2\": \(.*\)\$/\1/p" "$1" 2>/dev/null | head -n 1)"
  v="${v%,}"
  case "$v" in
    \"*\")
      v="${v#\"}"
      v="${v%\"}"
      v=${v//\\\"/\"}
      v=${v//\\\\/\\}
      ;;
  esac
  printf '%s' "$v"
}

_ci_lista() { _ci_campo "$1" "$2" | tr -d '[]",'; }

# --- Uso del script ----------------------------------------------------------------------------------------------------

_ci_uso() {
  awk 'NR == 1 && /^#!/ { next } /^# *shellcheck / { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$CI_SCRIPT"
}

# ci_abrir "$@": argumentos, carpeta de ejecución, inicio.json, cabecera y trampa de interrupción.
# Admite «-h», «--lista» y nombres de bloque. Un argumento que no es un bloque se ofrece a ci_argumento (si el
# script la define y devuelve 0, se acepta). Sale con 2 ante un argumento desconocido, sin tocar nada.
ci_abrir() {
  local a b rama commit nucleos docker="" es_bloque pedidos previo
  if [ -z "${CI_BLOQUES:-}" ]; then
    _ci_error "CI_BLOQUES está vacío: declara los bloques antes de ci_abrir"
    exit 2
  fi
  CI_SCRIPT="${CI_SCRIPT:-$0}"
  if [ -z "${ROOT:-}" ]; then
    ROOT="$(git -C "$(dirname "$CI_SCRIPT")" rev-parse --show-toplevel 2>/dev/null)" ||
      ROOT="$(cd "$(dirname "$CI_SCRIPT")/.." && pwd)"
  fi
  CI_NOMBRE="${CI_NOMBRE:-$(basename "$ROOT")}"
  CI_ELEGIDOS=""
  for a in "$@"; do
    case "$a" in
      -h | --help)
        _ci_uso
        exit 0
        ;;
      --lista)
        for b in $CI_BLOQUES; do echo "$b"; done
        exit 0
        ;;
      *)
        es_bloque=1
        case "$a" in -*) es_bloque=0 ;; esac
        # shellcheck disable=SC2086
        if [ $es_bloque -eq 1 ] && _ci_en "$a" $CI_BLOQUES; then
          CI_ELEGIDOS="$CI_ELEGIDOS $a"
        elif declare -F ci_argumento >/dev/null && ci_argumento "$a"; then
          :
        else
          case "$a" in
            -*) _ci_error "opción desconocida: $a (scripts/ci-local.sh -h)" ;;
            *) _ci_error "bloque desconocido: $a (scripts/ci-local.sh --lista)" ;;
          esac
          exit 2
        fi
        ;;
    esac
  done
  [ -n "$CI_ELEGIDOS" ] || CI_ELEGIDOS="$CI_BLOQUES"
  # Pedir un bloque arrastra lo que necesita (CI_NECESITA_<bloque>, sin límite de profundidad), y los elegidos quedan
  # en el orden declarado y sin repetir.
  pedidos="$CI_ELEGIDOS"
  previo=""
  while [ "$pedidos" != "$previo" ]; do
    previo="$pedidos"
    for b in $previo; do pedidos="$pedidos $(_ci_var "CI_NECESITA_$b")"; done
    CI_ELEGIDOS=""
    for b in $CI_BLOQUES; do
      # shellcheck disable=SC2086
      if _ci_en "$b" $pedidos; then CI_ELEGIDOS="$CI_ELEGIDOS $b"; fi
    done
    pedidos="$CI_ELEGIDOS"
  done
  # shellcheck disable=SC2086
  CI_ELEGIDOS="$(echo $CI_ELEGIDOS)"

  CI_DIR="${CI_LOCAL_LOGS:-$(_ci_base)/$(basename "$ROOT")}"
  if [ -f "$CI_DIR/inicio.json" ] && [ ! -f "$CI_DIR/fin" ]; then
    a="$(_ci_campo "$CI_DIR/inicio.json" pid)"
    if [ "$a" != "$$" ] && _ci_vivo "$a"; then
      _ci_error "ya hay un CI en marcha en esta copia (pid $a, registros en $CI_DIR): espera a que acabe o páralo"
      exit 2
    fi
  fi
  rm -rf "$CI_DIR" && mkdir -p "$CI_DIR" || {
    _ci_error "no se puede crear $CI_DIR"
    exit 2
  }
  export CI_DIR

  CI_INICIO=$(date +%s)
  rama="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  commit="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null)"
  nucleos="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo '?')"
  for b in $CI_ELEGIDOS; do
    # shellcheck disable=SC2086
    if _ci_en "$b" ${CI_DOCKER:-}; then docker="$docker $b"; fi
  done
  # shellcheck disable=SC2086
  _ci_escribir "$CI_DIR/inicio.json" m \
    "{" \
    "  \"estandar\": $CI_ESTANDAR," \
    "  \"lib\": \"$CI_LIB_VERSION\"," \
    "  \"nombre\": $(_ci_json_str "$CI_NOMBRE")," \
    "  \"ruta\": $(_ci_json_str "$ROOT")," \
    "  \"rama\": $(_ci_json_str "$rama")," \
    "  \"commit\": $(_ci_json_str "$commit")," \
    "  \"pid\": $$," \
    "  \"inicio\": $CI_INICIO," \
    "  \"bloques\": $(_ci_json_lista $CI_ELEGIDOS)," \
    "  \"docker\": $(_ci_json_lista $docker)" \
    "}"
  _CI_ARBOL0="$(git -C "$ROOT" status --porcelain 2>/dev/null | cksum)"
  trap '_ci_interrumpido' INT TERM
  echo "CI local de $CI_NOMBRE · $(date '+%Y-%m-%d %H:%M') · ${rama:-sin rama} · $nucleos núcleos · registros en $CI_DIR"
}

_ci_interrumpido() {
  local h
  trap - INT TERM
  for h in $(pgrep -P $$ 2>/dev/null); do _ci_matar_arbol "$h"; done
  echo >&2
  _ci_error "CI interrumpido: $CI_DIR queda sin «fin»"
  exit 130
}

ci_elegido() {
  # shellcheck disable=SC2086
  _ci_en "$1" $CI_ELEGIDOS
}

# ci_ok <bloque>: el bloque ya terminó en ok o aviso.
ci_ok() {
  local est=""
  [ -f "$CI_DIR/$1.estado" ] && read -r est _ <"$CI_DIR/$1.estado"
  case "$est" in ok | aviso) return 0 ;; *) return 1 ;; esac
}

# ci_esperar <bloque>: espera a que termine un bloque que corre en paralelo y devuelve como ci_ok. Si el bloque no está
# entre los elegidos, no espera y devuelve 0.
ci_esperar() {
  ci_elegido "$1" || return 0
  while [ ! -f "$CI_DIR/$1.estado" ]; do sleep 1; done
  ci_ok "$1"
}

# ci_abortar "<motivo>": para el CI antes de lanzar bloques (requisitos que faltan): escribe «fin» y sale con 2.
ci_abortar() {
  trap - INT TERM
  _ci_escribir "$CI_DIR/fin" m "fallo $(($(date +%s) - CI_INICIO)) $*"
  _ci_error "$*"
  exit 2
}

# --- Bloques -----------------------------------------------------------------------------------------------------------

# ci_correr <bloque> [orden…]: ejecuta la función del bloque (o la orden dada) desde la raíz del repo, con su límite de
# tiempo, y deja <bloque>.log, <bloque>.inicio, <bloque>.progreso y <bloque>.estado. La función devuelve 3 para
# «aviso». No hace nada si el bloque no está entre los elegidos. Devuelve 0 si queda en ok o aviso.
ci_correr() {
  local b="$1" t0 pid vigia_t vigia_p rc estado motivo="" lim pasos seg fn
  shift
  ci_elegido "$b" || return 0
  t0=$(date +%s)
  rm -f "$CI_DIR/$b.progreso" "$CI_DIR/.$b.paso" "$CI_DIR/.$b.limite"
  _ci_escribir "$CI_DIR/$b.inicio" m "$t0"
  pasos="$(_ci_var "CI_PASOS_$b")"
  if [ -z "$pasos" ]; then
    # Los pasos se cuentan en la función del bloque o en la que se pasa como orden (ci_correr build b_build).
    if [ $# -eq 0 ]; then fn="$b"; else fn="$1"; fi
    if declare -F "$fn" >/dev/null; then
      pasos="$(declare -f "$fn" | grep -o 'ci_paso' | wc -l | tr -d ' ')"
    else
      pasos=0
    fi
  fi
  lim="$(_ci_var "CI_LIMITE_$b")"
  lim="${lim:-${CI_LIMITE:-3600}}"
  echo "▶ $b"
  (
    _CI_BLOQUE="$b"
    _CI_PASOS="$pasos"
    _CI_PASO_I=0
    cd "$ROOT" || exit 1
    if [ $# -gt 0 ]; then "$@"; else "$b"; fi
  ) >"$CI_DIR/$b.log" 2>&1 </dev/null &
  pid=$!
  (
    sleep "$lim"
    : >"$CI_DIR/.$b.limite"
    _ci_matar_arbol "$pid" --duro
  ) >/dev/null 2>&1 &
  vigia_t=$!
  _ci_vigia_pruebas "$b" "$pid" >/dev/null 2>&1 &
  vigia_p=$!

  wait "$pid"
  rc=$?
  if [ -f "$CI_DIR/.$b.limite" ]; then
    wait "$vigia_t" 2>/dev/null
    estado=fallo
    motivo="límite superado (${lim} s)"
    rm -f "$CI_DIR/.$b.limite"
  else
    # shellcheck disable=SC2046
    kill $(pgrep -P "$vigia_t" 2>/dev/null) "$vigia_t" 2>/dev/null
    wait "$vigia_t" 2>/dev/null
    case $rc in 0) estado=ok ;; 3) estado=aviso ;; *) estado=fallo ;; esac
  fi
  # shellcheck disable=SC2046
  kill $(pgrep -P "$vigia_p" 2>/dev/null) "$vigia_p" 2>/dev/null
  wait "$vigia_p" 2>/dev/null
  _ci_escanear "$b"
  seg=$(($(date +%s) - t0))
  _ci_escribir "$CI_DIR/$b.estado" m "$estado $seg${motivo:+ $motivo}"
  case $estado in
    ok) echo "✔ $b ($(_ci_tiempo "$seg"))" ;;
    aviso) echo "! $b (aviso: $CI_DIR/$b.log)" ;;
    *) echo "✘ $b${motivo:+: $motivo} ($CI_DIR/$b.log)" ;;
  esac
  [ "$estado" != fallo ]
}

# ci_saltar <bloque> <motivo>: el bloque no se lanza (por ejemplo, porque falló otro del que depende).
ci_saltar() {
  ci_elegido "$1" || return 0
  _ci_escribir "$CI_DIR/$1.estado" m "saltado 0${2:+ $2}"
  echo "· $1 (saltado${2:+: $2})"
}

# ci_paso "<nombre>" <orden…>: marca el paso i de n del bloque en curso y ejecuta la orden. n se cuenta solo de las
# llamadas a ci_paso en la función del bloque (CI_PASOS_<bloque> lo fija a mano). Fuera de un bloque, solo ejecuta.
ci_paso() {
  local nombre="$1" n linea0
  shift
  if [ -z "${_CI_BLOQUE:-}" ]; then
    "$@"
    return
  fi
  _CI_PASO_I=$((_CI_PASO_I + 1))
  n="${_CI_PASOS:-0}"
  [ "$n" -ge "$_CI_PASO_I" ] 2>/dev/null || n="$_CI_PASO_I"
  linea0=$(wc -l <"$CI_DIR/$_CI_BLOQUE.log" | tr -d ' ')
  _ci_escribir "$CI_DIR/.$_CI_BLOQUE.paso" p "$_CI_PASO_I	$n	$linea0	$nombre"
  _ci_escribir "$CI_DIR/$_CI_BLOQUE.progreso" p "paso $_CI_PASO_I $n $nombre"
  echo "── $nombre"
  "$@"
}

# ci_secretos: gitleaks sobre el árbol y el historial, con scripts/ci-local.gitleaksignore si existe
# (CI_GITLEAKS_IGNORE lo cambia).
ci_secretos() {
  local ign="${CI_GITLEAKS_IGNORE:-$ROOT/scripts/ci-local.gitleaksignore}"
  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "Falta gitleaks (brew install gitleaks)"
    return 1
  fi
  if [ -f "$ign" ]; then
    ci_paso "Gitleaks" gitleaks git "$ROOT" --redact --no-banner --gitleaks-ignore-path "$ign"
  else
    ci_paso "Gitleaks" gitleaks git "$ROOT" --redact --no-banner
  fi
}

# ci_cerrar: espera a los bloques, imprime el resumen, enseña las últimas 25 líneas de los que fallan, escribe «fin» y
# sale con 0 (todo en ok, aviso o saltado) o 1. Si el script define ci_detalle <bloque>, su primera línea va junto a
# cada bloque en el resumen.
ci_cerrar() {
  local total fallos=0 b est seg resto det
  wait
  total=$(($(date +%s) - CI_INICIO))
  echo
  printf '%-18s %-10s %-8s %s\n' "BLOQUE" "ESTADO" "TIEMPO" "DETALLE"
  for b in $CI_ELEGIDOS; do
    est=sin-estado seg=0 resto="" det=""
    [ -f "$CI_DIR/$b.estado" ] && read -r est seg resto <"$CI_DIR/$b.estado"
    if declare -F ci_detalle >/dev/null; then det="$( (cd "$ROOT" && ci_detalle "$b") 2>/dev/null | head -n 1)"; fi
    printf '%-18s %-10s %-8s %s\n' "$b" "$est" "$(_ci_tiempo "$seg")" "$resto${resto:+${det:+ · }}$det"
    case "$est" in ok | aviso | saltado) ;; *) fallos=$((fallos + 1)) ;; esac
  done
  printf 'Total: %s\n' "$(_ci_tiempo "$total")"
  for b in $CI_ELEGIDOS; do
    est=sin-estado
    [ -f "$CI_DIR/$b.estado" ] && read -r est _ <"$CI_DIR/$b.estado"
    case "$est" in ok | aviso | saltado) continue ;; esac
    [ -f "$CI_DIR/$b.log" ] || continue
    echo
    echo "── $b: últimas líneas de $CI_DIR/$b.log"
    tail -n 25 "$CI_DIR/$b.log"
  done
  if [ "$(git -C "$ROOT" status --porcelain 2>/dev/null | cksum)" != "${_CI_ARBOL0:-}" ]; then
    echo
    echo "! Aviso: el árbol de git no está como al empezar (git status ha cambiado durante el CI)"
  fi
  trap - INT TERM
  if [ $fallos -gt 0 ]; then
    _ci_escribir "$CI_DIR/fin" m "fallo $total"
    echo
    echo "✘ $fallos bloque(s) sin pasar"
    exit 1
  fi
  _ci_escribir "$CI_DIR/fin" m "ok $total"
  echo
  echo "✔ Todo en verde"
  exit 0
}

# --- Avance por prueba -------------------------------------------------------------------------------------------------

# Lee el registro desde la línea «desde» y devuelve «<hechas> <total|?>» de la última herramienta reconocida (Flutter,
# Playwright, Vitest, pytest, Deno). Aproximado por diseño: sin total conocido, «?».
_CI_AWK='
NR <= desde { next }
{ l = $0; sub(/\r$/, "", l) }
l ~ /^Running [0-9]+ tests? using/ { split(l, f, " "); tool = "playwright"; tot = f[2] + 0; cnt = cnt + 0; next }
match(l, /^\[[0-9]+\/[0-9]+\]/) {
  s = substr(l, 2, RLENGTH - 2); split(s, f, "/"); tool = "playwright"
  if (f[1] + 0 > cnt + 0) cnt = f[1] + 0
  tot = f[2] + 0; next
}
l ~ /^ +[^ ]+ +[0-9]+ \[/ { split(l, f, " "); tool = "playwright"; if (f[2] + 0 > cnt + 0) cnt = f[2] + 0; next }
l ~ /^[0-9]+:[0-9]+ \+[0-9]+/ {
  m = split(l, f, " "); p = 0; s = 0; x = 0
  for (k = 2; k <= m && k <= 4; k++) {
    t = f[k]; ultimo = (t ~ /:$/); sub(/:$/, "", t)
    if (t ~ /^\+[0-9]+$/) p = substr(t, 2) + 0
    else if (t ~ /^~[0-9]+$/) s = substr(t, 2) + 0
    else if (t ~ /^-[0-9]+$/) x = substr(t, 2) + 0
    else break
    if (ultimo) break
  }
  tool = "flutter"; cnt = p + s + x
  if (l ~ /All tests passed!/ || l ~ /Some tests failed\./) tot = cnt; else tot = "?"
  next
}
l ~ /^ *Tests +[0-9]/ && match(l, /\([0-9]+\) *$/) { n = substr(l, RSTART + 1) + 0; tool = "vitest"; cnt = n; tot = n; next }
l ~ /Test Files/ { next }
l ~ /^ *[^ 0-9]/ && match(l, /\([0-9]+ tests?[ |)]/) {
  n = substr(l, RSTART + 1) + 0
  if (tool != "vitest") { tool = "vitest"; cnt = 0; tot = "?" }
  cnt += n; next
}
match(l, /collected [0-9]+ items?/) {
  tool = "pytest"; tot = substr(l, RSTART + 10) + 0
  if (match(l, /[0-9]+ selected/)) tot = substr(l, RSTART) + 0
  cnt = 0; next
}
l ~ /^\[gw[0-9]+\] \[ *[0-9]+%\] (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)/ { tool = "pytest"; cnt++; next }
l ~ /\[ *[0-9]+%\] *$/ {
  tool = "pytest"; cnt = cnt + 0
  if (l ~ /::/) { cnt++; next }
  t = l; sub(/\[ *[0-9]+%\] *$/, "", t); m = split(t, f, " ")
  for (k = 1; k <= m; k++) if (f[k] ~ /^[.FEsxXR]+$/) cnt += length(f[k])
  next
}
l ~ /^(ok|FAILED) \| [0-9]+ passed/ {
  m = split(l, f, " "); n = 0
  for (k = 2; k <= m; k++) if (f[k] ~ /^(passed|failed|ignored)/ && f[k - 1] ~ /^[0-9]+$/) n += f[k - 1]
  tool = "deno"; cnt = n; tot = n; next
}
l ~ /^[^ ].* \.\.\. (ok|FAILED|ignored)/ { if (tool != "deno") { tool = "deno"; cnt = 0; tot = "?" }; cnt++; next }
END { if (tool != "") print cnt + 0, tot }
'

_ci_contar() { awk -v desde="${2:-0}" "$_CI_AWK" "$1" 2>/dev/null; }

# Recalcula la línea «prueba» del paso en curso del bloque y la escribe en <bloque>.progreso.
_ci_escanear() {
  local b="$1" i="" n="" desde=0 nombre="" r
  [ -f "$CI_DIR/$b.log" ] || return 0
  if [ -f "$CI_DIR/.$b.paso" ]; then
    IFS='	' read -r i n desde nombre <"$CI_DIR/.$b.paso"
  fi
  r="$(_ci_contar "$CI_DIR/$b.log" "${desde:-0}")"
  [ -n "$r" ] || return 0
  if [ -n "$i" ]; then
    _ci_escribir "$CI_DIR/$b.progreso" w "paso $i $n $nombre" "prueba $r"
  else
    _ci_escribir "$CI_DIR/$b.progreso" w "prueba $r"
  fi
}

_ci_vigia_pruebas() {
  while _ci_vivo "$2"; do
    _ci_escanear "$1"
    sleep 1
  done
}

# --- Estado (lib.sh estado) --------------------------------------------------------------------------------------------

_ci_progreso_texto() {
  local f="$1" solo_prueba="${2:-}" k a n resto paso="" prueba=""
  [ -f "$f" ] || return 0
  while read -r k a n resto; do
    case "$k" in
      paso) paso="paso $a/$n${resto:+ $resto}" ;;
      prueba) prueba="prueba $a/$n" ;;
    esac
  done <"$f"
  if [ -n "$solo_prueba" ]; then
    printf '%s' "$prueba"
  else
    printf '%s' "$paso${paso:+${prueba:+ · }}$prueba"
  fi
}

_ci_estado() {
  local d="$1" nombre rama commit pid inicio bloques docker ahora vivo=0 cab b est seg resto t0 icono p extra
  nombre="$(_ci_campo "$d/inicio.json" nombre)"
  rama="$(_ci_campo "$d/inicio.json" rama)"
  commit="$(_ci_campo "$d/inicio.json" commit)"
  pid="$(_ci_campo "$d/inicio.json" pid)"
  inicio="$(_ci_campo "$d/inicio.json" inicio)"
  bloques="$(_ci_lista "$d/inicio.json" bloques)"
  docker="$(_ci_lista "$d/inicio.json" docker)"
  ahora=$(date +%s)
  if [ ! -f "$d/fin" ] && _ci_vivo "$pid"; then vivo=1; fi
  if [ -f "$d/fin" ]; then
    read -r est seg resto <"$d/fin"
    cab="$est en $(_ci_tiempo "$seg") · empezó a las $(_ci_hora "$inicio")${resto:+ · $resto}"
  elif [ $vivo -eq 1 ]; then
    cab="en marcha desde hace $(_ci_tiempo $((ahora - inicio)))"
  else
    cab="interrumpido (empezó a las $(_ci_hora "$inicio"), el proceso $pid ya no existe)"
  fi
  echo "CI local de $nombre · $rama${commit:+@$commit} · $cab"
  echo "  $d"
  if [ $vivo -eq 1 ] && [ -n "${docker// /}" ]; then echo "  usa Docker:$(printf ' %s' $docker)"; fi
  for b in $bloques; do
    extra=""
    if [ -f "$d/$b.estado" ]; then
      read -r est seg resto <"$d/$b.estado"
      case "$est" in ok) icono="✔" ;; aviso) icono="!" ;; saltado) icono="·" ;; *) icono="✘" ;; esac
      p="$(_ci_progreso_texto "$d/$b.progreso" solo)"
      extra="${resto:-}${resto:+${p:+ · }}$p"
      printf '  %s %-18s %-10s %-7s %s\n' "$icono" "$b" "$est" "$(_ci_tiempo "$seg")" "$extra"
    elif [ -f "$d/$b.inicio" ]; then
      read -r t0 <"$d/$b.inicio"
      if [ $vivo -eq 1 ]; then
        printf '  %s %-18s %-10s %-7s %s\n' "⏳" "$b" "en marcha" "$(_ci_tiempo $((ahora - t0)))" "$(_ci_progreso_texto "$d/$b.progreso")"
      else
        printf '  %s %-18s %-10s\n' "✘" "$b" "cortado"
      fi
    elif [ $vivo -eq 1 ]; then
      printf '  %s %-18s %-10s\n' "…" "$b" "en cola"
    else
      printf '  %s %-18s %-10s\n' "·" "$b" "sin correr"
    fi
  done
}

_ci_cmd_estado() {
  local base d raiz hay=0
  base="$(_ci_base)"
  case "${1:-}" in
    --todos)
      # shellcheck disable=SC2045
      for d in $(ls -t "$base" 2>/dev/null); do
        [ -f "$base/$d/inicio.json" ] || continue
        [ $hay -eq 1 ] && echo
        hay=1
        _ci_estado "$base/$d"
      done
      [ $hay -eq 1 ] || echo "No hay ejecuciones de CI local en $base"
      ;;
    "")
      raiz="$(git rev-parse --show-toplevel 2>/dev/null)" || {
        _ci_error "no estás en un repo: usa «lib.sh estado <carpeta>» o «lib.sh estado --todos»"
        return 2
      }
      d="${CI_LOCAL_LOGS:-$base/$(basename "$raiz")}"
      if [ ! -f "$d/inicio.json" ]; then
        echo "No hay ejecuciones de CI local de $(basename "$raiz") en $d"
        return 1
      fi
      _ci_estado "$d"
      ;;
    *)
      if [ ! -f "$1/inicio.json" ]; then
        _ci_error "no hay inicio.json en $1"
        return 2
      fi
      _ci_estado "$1"
      ;;
  esac
}

_ci_main() {
  local r
  case "${1:-}" in
    estado)
      shift
      _ci_cmd_estado "$@"
      ;;
    contar)
      [ -f "${2:-}" ] || {
        _ci_error "uso: lib.sh contar <registro>"
        return 2
      }
      r="$(_ci_contar "$2" 0)"
      if [ -n "$r" ]; then echo "prueba $r"; fi
      ;;
    version | --version) echo "$CI_LIB_VERSION (estándar v$CI_ESTANDAR)" ;;
    *)
      echo "uso: lib.sh estado [carpeta|--todos] | contar <registro> | version" >&2
      return 2
      ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _ci_main "$@"
  exit $?
fi
