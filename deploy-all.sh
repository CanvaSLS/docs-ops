#!/usr/bin/env bash
# deploy-all.sh · despliega TODO el backend en el orden correcto y deja listas las URLs del frontend.
#
#   ./deploy-all.sh                 # stage dev, los 6 servicios
#   ./deploy-all.sh dev --sin-practica
#   ./deploy-all.sh dev --solo ms-auth,ms-cursos      # un subconjunto (p. ej. para probar TU servicio)
#
# Requisitos: Node 18+, Python 3 con pip (y internet), credenciales del Learner Lab vigentes (README, paso 2) y
#             export DB_PASSWORD='...'   contraseña de la RDS (8+ caracteres, sin / @ " ni espacios).
#             La RDS (infra-base) tarda ~10 min en crearse la primera vez: es normal.
# Orden: infra-base (SNS + S3) → ms-auth (authorizer) → ms-cursos → ms-evaluaciones → ms-analitica → ms-notificaciones → ms-practica
set -euo pipefail

STAGE="${1:-dev}"; shift || true
SOLO=""; PRACTICA=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sin-practica) PRACTICA=0 ;;
    --solo) SOLO="$2"; shift ;;
    *) echo "Opción desconocida: $1"; exit 2 ;;
  esac; shift
done

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAIZ:-$(cd "$AQUI/.." && pwd)}"         # carpeta que contiene ms-auth/, ms-cursos/, infra-base/, ...
SLS="${SLS:-npx --yes serverless@3}"             # Serverless Framework v3 (como en clase). Cambia con SLS="serverless"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export SLS_TELEMETRY_DISABLED=1

SERVICIOS=(infra-base ms-auth ms-cursos ms-evaluaciones ms-analitica ms-notificaciones)
[[ $PRACTICA -eq 1 ]] && SERVICIOS+=(ms-practica)

echo "▶ Verificando credenciales de AWS…"
if command -v aws >/dev/null 2>&1; then
  aws sts get-caller-identity --query '[Account,Arn]' --output text \
    || { echo "✗ Credenciales inválidas o vencidas (duran ~4 h). Vuelve a copiarlas desde Learner Lab → AWS Details → AWS CLI → Show"; exit 1; }
elif [[ -z "${AWS_ACCESS_KEY_ID:-}" && ! -f "$HOME/.aws/credentials" ]]; then
  echo "✗ No encuentro credenciales (~/.aws/credentials ni variables AWS_*)"; exit 1
fi

quiere() { [[ -z "$SOLO" ]] || [[ ",$SOLO," == *",$1,"* ]]; }
mkdir -p "$AQUI/salida"; : > "$AQUI/salida/apis.env"

if quiere infra-base || quiere ms-cursos || quiere ms-evaluaciones; then
  [[ -n "${DB_PASSWORD:-}" ]] || { echo "✗ Falta DB_PASSWORD (contraseña de la RDS). Exporta:  export DB_PASSWORD='<8+ caracteres, sin / @ \" ni espacios>'"; exit 1; }
  [[ "$DB_PASSWORD" =~ ^[^/@\"[:space:]]{8,}$ ]] || { echo "✗ DB_PASSWORD debe tener 8+ caracteres y no usar / @ \" ni espacios"; exit 1; }
fi

if quiere ms-auth; then
  falta_auth=0
  [[ "${TENANT_INVITE_CODES:-}" == "{"* ]] || {
    echo "✗ Falta TENANT_INVITE_CODES (objeto JSON con los códigos de invitación por tenant)."
    falta_auth=1
  }
  [[ -n "${FRONTEND_ORIGIN:-}" && "${FRONTEND_ORIGIN:-}" != */ ]] || {
    echo "✗ Falta FRONTEND_ORIGIN (origen del frontend, sin barra final)."
    falta_auth=1
  }
  if [[ $falta_auth -ne 0 ]]; then
    cat <<'AYUDA'
  Exporta ambas antes de desplegar ms-auth, por ejemplo:
    export TENANT_INVITE_CODES='{"UTEC":"<codigo>","NORTE":"<codigo>","ANDINO":"<codigo>"}'
    export FRONTEND_ORIGIN='https://<tu-app>.amplifyapp.com'
AYUDA
    exit 1
  fi
fi

empaquetar_driver() {   # pymysql es Python puro: se instala en ./vendor y viaja dentro del zip de la Lambda
  echo "  · instalando pymysql en $1/vendor"
  python3 -m pip install --quiet --upgrade -r "$RAIZ/$1/requirements.txt" -t "$RAIZ/$1/vendor" \
    || { echo "✗ pip no pudo instalar pymysql (¿sin internet?)"; exit 1; }
}

url_base() {   # extrae https://<id>.execute-api.<region>.amazonaws.com/<stage> de `sls info`
  (cd "$RAIZ/$1" && $SLS info --stage "$STAGE" 2>/dev/null | grep -Eo 'https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com/[A-Za-z0-9_-]+' | head -1) || true
}

for s in "${SERVICIOS[@]}"; do
  quiere "$s" || continue
  echo; echo "══════════ $s ══════════"
  [[ "$s" == "ms-cursos" || "$s" == "ms-evaluaciones" ]] && empaquetar_driver "$s"
  (cd "$RAIZ/$s" && $SLS deploy --stage "$STAGE")
done

DB_ENDPOINT=""
if command -v aws >/dev/null 2>&1; then
  DB_ENDPOINT="$(aws cloudformation describe-stacks --stack-name "sp-infra-$STAGE" \
    --query "Stacks[0].Outputs[?OutputKey=='DbEndpoint'].OutputValue" --output text 2>/dev/null || true)"
fi

echo; echo "▶ Recolectando URLs…"
# macOS trae bash 3.2, sin arreglos asociativos: el mapeo servicio→variable va en funciones.
var_de() {
  case "$1" in
    ms-auth) echo AUTH ;;
    ms-cursos) echo CURSOS ;;
    ms-evaluaciones) echo EVAL ;;
    ms-analitica) echo ANALITICA ;;
    ms-notificaciones) echo NOTIF ;;
    ms-practica) echo PRACTICA ;;
  esac
}
clave_de() {
  case "$1" in
    ms-auth) echo auth ;;
    ms-cursos) echo cursos ;;
    ms-evaluaciones) echo eval ;;
    ms-analitica) echo analitica ;;
    ms-notificaciones) echo notif ;;
    ms-practica) echo practica ;;
  esac
}
JSON="{"
for s in ms-auth ms-cursos ms-evaluaciones ms-analitica ms-notificaciones ms-practica; do
  [[ -d "$RAIZ/$s" ]] || continue
  u="$(url_base "$s")"
  [[ -n "$u" ]] || { echo "  (sin URL para $s: ¿está desplegado?)"; continue; }
  echo "VITE_API_$(var_de "$s")=$u" | tee -a "$AQUI/salida/apis.env"
  JSON+="\"$(clave_de "$s")\":\"$u\","
done
echo "${JSON%,}}" > "$AQUI/salida/apis.json"

cat <<MSG

✔ Listo.
  • Pega las líneas VITE_API_* en Amplify → Hosting → Environment variables (y redeploy del frontend).
  • Prueba de humo:   python3 $AQUI/smoke_test.py --apis $AQUI/salida/apis.json
  • Datos de prueba (RDS + DynamoDB), desde tu computadora:
        pip install -r $RAIZ/datos-seed/requirements.txt
        export DB_HOST=${DB_ENDPOINT:-<DbEndpoint de infra-base>} DB_USER=admin DB_PASSWORD=...   # la misma contraseña
        python3 $RAIZ/datos-seed/seed.py
  • Evidencia (30k+): python3 $RAIZ/datos-seed/verify_counts.py   (con las mismas variables DB_*)
  • Swagger:          copia salida/apis.json a frontend-web/public/docs/apis.json
MSG
