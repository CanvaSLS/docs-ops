#!/usr/bin/env bash
# push-all.sh · crea (si hace falta) y sube cada carpeta como repositorio PÚBLICO de la organización CanvaSLS.
#   ./push-all.sh "mensaje del commit"
# Requiere `gh auth login` (o un repo ya creado + credenciales git). NUNCA sube credenciales: ver .gitignore.
set -euo pipefail
ORG="${ORG:-CanvaSLS}"; MSG="${1:-chore: actualización}"
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="${RAIZ:-$(cd "$AQUI/.." && pwd)}"
REPOS=(infra-base ms-auth ms-cursos ms-evaluaciones ms-analitica ms-notificaciones ms-practica datos-seed pruebas-locales docs-ops)
for r in "${REPOS[@]}"; do
  [[ -d "$RAIZ/$r" ]] || continue
  echo "── $ORG/$r"
  cd "$RAIZ/$r"
  [[ -d .git ]] || git init -q -b main
  # candado: jamás subir llaves ni sesiones de AWS
  if grep -rIlE 'aws_secret_access_key *[=:] *[A-Za-z0-9/+]{30,}|aws_session_token *[=:] *[A-Za-z0-9/+=]{60,}|(AKIA|ASIA)[0-9A-Z]{16}' --exclude-dir=.git --exclude=push-all.sh . | grep -q .; then
    echo "✗ Se detectaron credenciales de AWS en $r: aborto."; exit 1
  fi
  git add -A
  git diff --cached --quiet || git commit -q -m "$MSG"
  if ! git remote get-url origin >/dev/null 2>&1; then
    if command -v gh >/dev/null 2>&1; then
      gh repo view "$ORG/$r" >/dev/null 2>&1 || gh repo create "$ORG/$r" --public --description "CanvaSLS · $r" >/dev/null
    fi
    git remote add origin "https://github.com/$ORG/$r.git"
  fi
  git push -q -u origin main && echo "   ✔ https://github.com/$ORG/$r"
done
