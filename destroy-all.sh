#!/usr/bin/env bash
# destroy-all.sh · elimina los stacks (orden inverso). Vacía el bucket S3 antes (CloudFormation no borra buckets con objetos).
#   ./destroy-all.sh [stage]
set -euo pipefail
STAGE="${1:-dev}"
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="${RAIZ:-$(cd "$AQUI/.." && pwd)}"
SLS="${SLS:-npx --yes serverless@3}"; export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
read -r -p "¿Eliminar TODO el backend ($STAGE)? Las tablas DynamoDB y su seed se pierden. Escribe SI: " ok
[[ "$ok" == "SI" ]] || { echo "Cancelado"; exit 1; }
if command -v aws >/dev/null 2>&1; then
  CUENTA="$(aws sts get-caller-identity --query Account --output text)"
  aws s3 rm "s3://sp-storage-${CUENTA}-${STAGE}" --recursive 2>/dev/null || true
fi
for s in ms-practica ms-notificaciones ms-analitica ms-evaluaciones ms-cursos ms-auth infra-base; do
  [[ -d "$RAIZ/$s" ]] || continue
  echo "── removiendo $s"; (cd "$RAIZ/$s" && $SLS remove --stage "$STAGE") || echo "  (ya no existía)"
done
