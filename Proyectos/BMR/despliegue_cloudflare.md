# Despliegue en CloudFlare Pages

Este documento explica cómo funcionan los enlaces generados al momento de publicar el proyecto del árbol genealógico en CloudFlare Pages.

Al ejecutar el comando de despliegue, CloudFlare genera típicamente dos tipos de enlaces:

## 1. URL Principal (Alias de Producción)
Ejemplo: `https://master.bmr-arbol.pages.dev`

- **Qué es:** Es el enlace oficial de producción de la página. 
- **Para qué sirve:** Siempre apunta a la **última versión** que se haya subido. Este es el enlace que se debe compartir con los familiares o usuarios finales, ya que se actualizará automáticamente cada vez que se haga un nuevo despliegue.

## 2. URL de Despliegue Específico (Preview/Commit)
Ejemplo: `https://1183f97d.bmr-arbol.pages.dev`

- **Qué es:** Es un enlace inmutable generado a partir de un código hash único (ej. `1183f97d`).
- **Para qué sirve:** Funciona como una "fotografía" o captura exacta de la página en el momento exacto en el que se hizo esa subida en particular.
- **Utilidad:** Es extremadamente útil para control de versiones. Si en un futuro se sube una actualización que contiene un error, los enlaces específicos anteriores seguirán funcionando intactos, permitiendo revisar versiones pasadas de la página. Para el uso diario se puede ignorar.

---
**Nota:** Para realizar un nuevo despliegue en caso de cambios, asegúrate de tener Node.js instalado y ejecuta:
```bash
npx wrangler pages deploy web
```

> [!NOTE]
> **Sobre la Autenticación:** 
> Si ejecutas el comando en **esta máquina**, no necesitas volver a autenticarte porque las credenciales ya están guardadas. Sin embargo, si en el futuro cambias de computadora o expira la sesión, al ejecutar el comando Wrangler abrirá automáticamente una ventana en tu navegador para que inicies sesión en tu cuenta de CloudFlare.
