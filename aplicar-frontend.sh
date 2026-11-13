#!/usr/bin/env bash
# aplicar-frontend.sh · copia el kit conectado a AWS dentro de tu repo frontend-web (no borra nada tuyo).
#   ./aplicar-frontend.sh /ruta/a/frontend-web
set -euo pipefail
DEST="${1:?Uso: ./aplicar-frontend.sh /ruta/a/frontend-web}"
AQUI="$(cd "$(dirname "$0")" && pwd)"; KIT="$AQUI/../frontend-kit"
[[ -f "$DEST/package.json" ]] || { echo "✗ $DEST no parece un proyecto Vite"; exit 1; }
mkdir -p "$DEST/src/live" "$DEST/public/docs"
cp "$KIT"/src/live/* "$DEST/src/live/"
cp "$KIT/src/main.tsx" "$DEST/src/main.tsx"
cp "$KIT/public/docs/"* "$DEST/public/docs/"
cp -n "$KIT/.env.example" "$DEST/.env.example" || true
[[ -f "$AQUI/salida/apis.json" ]] && cp "$AQUI/salida/apis.json" "$DEST/public/docs/apis.json" || true
cat <<MSG
✔ Kit aplicado. Siguiente:
  cd $DEST && npm install && npm run build        # debe compilar sin errores de tipos
  Crea .env.local con las VITE_API_* (salida/apis.env) y prueba:  npm run dev
MSG
