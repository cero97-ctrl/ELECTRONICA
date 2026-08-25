# Conversación: Superando Errores 403 y Bloqueos de Seguridad en Agentes IA

## Usuario
A veces cuando mis agentes ia consultan alguna página web en la internet, en busqueda de información, las páginas devuelven error 403. Sabes lo qu significa?

## Asistente
El error **403 Forbidden** (Prohibido) significa que el servidor web entiende perfectamente la solicitud, pero se niega a autorizar el acceso a la página. A diferencia del error 404 (página no encontrada), el 403 es un bloqueo intencional impuesto por el servidor.

Cuando esto ocurre en la interacción de agentes de IA y sistemas de extracción de datos, casi siempre se debe a que las medidas de seguridad del sitio web han detectado que la visita es automatizada y no proviene de un humano usando un navegador convencional.

Dado que las herramientas en la capa de ejecución de tus agentes operan con scripts de Python, aquí están los motivos más comunes por los que los servidores levantan esta barrera:

### 1. El "User-Agent" por defecto
Cada vez que se hace una petición web, se envía un encabezado llamado `User-Agent` que identifica qué software está realizando la consulta. Librerías comunes como `requests` o `urllib` envían por defecto firmas como `python-requests/2.31.0`. Los cortafuegos y sistemas de seguridad de los sitios web tienen listas negras que bloquean estas firmas de forma inmediata.

### 2. Falta de encabezados de navegador
Un navegador real (como Chrome o Firefox) no solo envía el `User-Agent`, sino una docena de encabezados adicionales (headers) como `Accept-Language`, `Sec-Fetch-Site`, o `Accept-Encoding`. Si el script de tu agente realiza una petición "desnuda" sin imitar esta estructura compleja, los sistemas de protección lo identifican rápidamente como un bot.

### 3. Bloqueos por IP y Límites de Tasa (Rate Limiting)
Si el agente consulta la misma página o dominio repetidas veces en un periodo muy corto, el servidor detecta el patrón no humano de navegación. Esto dispara los sistemas anti-DDoS (como Cloudflare o Akamai), los cuales bloquean temporal o permanentemente la dirección IP.

### 4. Desafíos de JavaScript (Anti-Bots)
Muchos sitios web modernos requieren que el cliente pueda renderizar y ejecutar código JavaScript en segundo plano para validar que es un navegador legítimo o para generar un token de acceso dinámico. Como las peticiones HTTP estándar de Python no ejecutan JavaScript, fallan este "desafío invisible" y reciben un 403.

---

## Usuario
Muéstrame cómo configurar un User-Agent falso y encabezados en mis scripts de Python para evitar los bloqueos 403.

## Asistente
Para dotar a la capa de ejecución de tus agentes de un camuflaje efectivo, puedes modificar las peticiones de librerías como `requests` para que sean idénticas a las que haría un humano navegando.

La clave no es solo cambiar el `User-Agent`, sino incluir todo el paquete de encabezados (headers) que los servidores modernos esperan ver y rotarlos dinámicamente para no crear un patrón predecible.

Aquí tienes un script base en Python que puedes integrar como herramienta para tus agentes:

```python
import requests
import random

# Diccionario de User-Agents recientes para rotar
USER_AGENTS = [
    # Chrome en Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Safari en macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    # Firefox en Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
]

def obtener_html_seguro(url):
    """
    Realiza una petición HTTP GET simulando un navegador real para evitar el error 403.
    """
    
    # Construcción de los encabezados imitando un navegador convencional
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        # Indica qué tipo de contenido puede procesar el navegador
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        # Simula preferencias de idioma realistas
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        # Indica soporte para compresión de datos
        "Accept-Encoding": "gzip, deflate, br",
        # Evita que el servidor cierre la conexión inmediatamente
        "Connection": "keep-alive",
        # Metadatos de seguridad que los navegadores modernos siempre envían
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1"
    }

    try:
        # El timeout es vital para que el agente no se quede colgado indefinidamente
        response = requests.get(url, headers=headers, timeout=10)
        
        # Lanza una excepción si el código HTTP es un error (como 403 o 404)
        response.raise_for_status() 
        
        return response.text

    except requests.exceptions.HTTPError as e:
        print(f"Bloqueo detectado o página no encontrada: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        return None

# Ejemplo de uso de la herramienta
url_objetivo = "https://ejemplo.com"
html_obtenido = obtener_html_seguro(url_objetivo)

if html_obtenido:
    print("Petición exitosa. El servidor nos ha tratado como un humano.")
```

### Por qué funciona esta estructura
1. **Rotación de User-Agent:** Si tu agente hace múltiples consultas, usar siempre la misma firma levanta sospechas. El script elige una firma de sistema operativo y navegador diferente al azar en cada petición.
2. **Encabezados `Sec-Fetch-*`:** Los sistemas anti-bots modernos revisan estos metadatos. Indican al servidor que la petición proviene de un intento de navegación real (hacer clic en un enlace o escribir una URL), no de un script de extracción.
3. **`Accept-Language` y `Accept-Encoding`:** Un script básico de Python solo pide el HTML crudo. Un navegador real siempre avisa qué idiomas prefiere y qué formatos de compresión (`gzip`, `br`) soporta.

> **Consejo avanzado:** Si prefieres no mantener la lista de `USER_AGENTS` actualizada manualmente, puedes instalar la librería `fake_useragent` (`pip install fake-useragent`). Esta librería genera dinámicamente firmas de navegadores recientes y reales bajo demanda.

---

## Usuario
¿Qué herramientas puedo usar si, incluso con estos encabezados, la página me bloquea usando Cloudflare o desafíos de JavaScript?

## Asistente
Cuando te enfrentas a escudos como Cloudflare, Datadome o Akamai, los encabezados ya no son suficientes. Estos sistemas no solo leen el texto de la petición, sino que analizan la **huella TLS** (cómo se encripta la conexión a nivel de red) y ejecutan rutinas complejas de JavaScript para buscar propiedades que solo un motor de renderizado real posee.

Para superar estas barreras en la capa de ejecución de tus agentes, existen herramientas especializadas en Python. Al operar en un entorno GNU/Linux con 4GB de RAM, el consumo de memoria dictará qué estrategia es la más viable para tus scripts, ya que la emulación de navegadores es un proceso pesado.

Aquí tienes las mejores opciones ordenadas de menor a mayor consumo de recursos:

### 1. Librerías de suplantación TLS (Alta eficiencia)
Estas herramientas no abren un navegador visual, sino que modifican la forma en que Python negocia la conexión criptográfica para que sea matemáticamente idéntica a la de Chrome o Firefox. Son ideales para hardware con recursos limitados.

*   **`curl_cffi`:** Es actualmente una de las herramientas más potentes. Actúa como un puente hacia la librería en C de cURL, permitiendo suplantar (spoofing) la huella TLS (JA3/JA4) de navegadores reales. Para los sistemas de seguridad, la petición se ve exactamente igual a la de un Chrome moderno.
*   **`cloudscraper`:** Una extensión directa de `requests` diseñada específicamente para resolver los desafíos matemáticos de JavaScript que Cloudflare inyecta antes de cargar la página. No funciona con los desafíos más nuevos (como los captchas interactivos de Turnstile), pero es excelente para bloqueos de nivel medio.

### 2. Navegadores Headless Indetectables (Alto consumo de RAM)
Si la página web utiliza Cloudflare Turnstile (el desafío que pide marcar una casilla o que se resuelve solo tras analizar los movimientos del mouse), necesitarás levantar un navegador real en segundo plano (modo *headless*). 

*   **`undetected-chromedriver`:** Es una versión parcheada de Selenium. El ChromeDriver normal "grita" a los cuatro vientos que es un bot porque expone variables globales en JavaScript (como `navigator.webdriver = true`). Esta librería elimina todas esas huellas, permitiendo que el script navegue sin ser detectado.
*   **`Playwright` + `playwright-stealth`:** Playwright es una alternativa moderna y más rápida a Selenium, desarrollada por Microsoft. Al agregarle el plugin *stealth*, enmascara las propiedades del bot de manera muy efectiva.

**Precaución de memoria:** Levantar instancias de Chromium en segundo plano consumirá rápidamente la memoria disponible. Si optas por estas herramientas, es vital programar tu agente para que inicie el navegador, extraiga el DOM (HTML) y ejecute un cierre estricto (`browser.quit()`) de forma inmediata para liberar la RAM antes de que el LLM orquestador continúe con el procesamiento.

### 3. APIs de Scraping (Cero consumo local)
Si el objetivo es extremadamente hostil y el consumo de RAM bloquea al agente, la alternativa es delegar la extracción.

*   Servicios como **ScraperAPI** o **ScrapingBee** actúan como intermediarios. Tu agente envía una petición HTTP normal a la API de estos servicios, y los servidores de ellos se encargan de levantar los navegadores, resolver los captchas de Cloudflare, rotar las IPs residenciales y devolverle a tu agente el HTML limpio.
