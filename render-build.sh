#!/usr/bin/env bash
# Build de Render para SIAM: instala dependencias del sistema requeridas por
# WeasyPrint (Pango/GTK) antes de instalar las dependencias de Python.
# Sin estas librerías, el import de weasyprint falla o write_pdf() lanza OSError.
set -euo pipefail

echo "==> [render-build] Instalando dependencias del sistema para WeasyPrint (Pango)"
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    fonts-dejavu-core || echo "==> [render-build] AVISO: apt-get no completó; el PDF podría fallar en runtime"
else
  echo "==> [render-build] AVISO: apt-get no disponible; saltando dependencias del sistema"
fi

echo "==> [render-build] Instalando dependencias de Python"
pip install -r requirements.txt

echo "==> [render-build] Build completado"