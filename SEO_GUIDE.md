# Guía SEO para SIAM

## Registrar el sitio en Google Search Console

1. Ve a https://search.google.com/search-console
2. Inicia sesión con tu cuenta de Google
3. Agrega tu propiedad (dominio o prefijo URL)
4. **Verificación**: El proyecto ya incluye verificación automática mediante:
   - `sitemap.xml` en `/sitemap.xml`
   - Meta tags SEO en todas las páginas
   - Datos estructurados Schema.org
5. Opcional: sube el archivo `googleXXXXXX.html` a `/static/` si usas verificación por archivo

## Archivos SEO incluidos

| Archivo | Ruta | Propósito |
|---------|------|-----------|
| `robots.txt` | `/robots.txt` | Instrucciones para crawlers |
| `sitemap.xml` | `/sitemap.xml` | Mapa del sitio para Google |
| `manifest.json` | `/manifest.json` | PWA manifest |
| `favicon.ico` | `/favicon.ico` | Favicon |
| `favicon.svg` | `/static/favicon.svg` | Favicon SVG |

## Meta Tags implementados

- **title** dinámico por página (block `title`)
- **meta description** personalizable (block `meta_description`)
- **meta keywords** personalizable (block `meta_keywords`)
- **Open Graph** (og:title, og:description, og:image, og:url, og:type, og:locale)
- **Twitter Cards** (twitter:card, twitter:title, twitter:description)
- **Canonical URL** (block `canonical_url`)
- **Schema.org** (SoftwareApplication con nombre, descripción, categoría, URL)

## Datos Estructurados (Schema.org)

El proyecto incluye Schema.org tipo `SoftwareApplication` con:
- `name`: SIAM
- `description`: Sistema Integral Automotriz
- `applicationCategory`: BusinessApplication
- `operatingSystem`: Web
- `url`: URL del sitio
- `author`: SIAM SAS

## Recomendaciones adicionales

1. **Google Analytics**: Agrega tu código GA en `base.html`
2. **Google Tag Manager**: Útil para gestión de etiquetas
3. **Imagen OG**: Crea `/static/img/og-image.png` (1200x630px)
4. **PageSpeed**: Optimiza imágenes y recursos para mejorar puntuación
5. **Backlinks**: Consigue enlaces de calidad hacia el sitio
6. **Contenido**: Mantén el sitio actualizado con contenido relevante

## Verificar indexación

```bash
# En Google Search Console:
1. Ve a "Inspección de URLs"
2. Ingresa https://tudominio.com
3. Solicita indexación
```

O usa:
```
https://www.google.com/search?q=site:tudominio.com
```
