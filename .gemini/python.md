# Registro de Errores en Scripts Python

Este archivo documenta errores comunes encontrados al ejecutar scripts Python en este espacio de trabajo, junto con sus respectivas soluciones para evitar regresiones.

---

## 1. `PromptTemplate` de LangChain Falla con Contenido LaTeX que Contiene Llaves Numéricas

### Síntoma / Mensaje de Error

Al ejecutar un script que usa `PromptTemplate` de LangChain para procesar contenido LaTeX, el script falla con el siguiente error:

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for PromptTemplate
  Value error, Invalid variable name '10' in f-string template. Variable names
  cannot be all digits as they are interpreted as positional arguments.
  [type=value_error, input_value={'template': '...', 'template_format': 'f-string'}, input_type=dict]
```

### Causa

Por defecto, `PromptTemplate` de LangChain usa `template_format='f-string'`, que interpreta cualquier contenido entre llaves simples `{...}` como una variable. Cuando el contenido LaTeX inyectado contiene comandos del paquete `siunitx` como `\SI{10}{\kilo\ohm}`, `\SI{100}{\micro\farad}`, o cualquier otra llave con números (`{20}`, `{2.5}`, etc.), Python los interpreta como argumentos posicionales de f-string, lo cual es inválido y lanza un `ValidationError` de Pydantic.

El problema se manifiesta al pasar el código LaTeX como variable al template:

```python
# El contenido LaTeX contiene cosas como: \SI{10}{\kilo\ohm}
# Python ve {10} y lo interpreta como un argumento posicional de f-string
prompt = PromptTemplate(
    template="Analiza esto: {latex_code}",  # f-string por defecto
    input_variables=["latex_code"],
)
chain.invoke({"latex_code": contenido_con_llaves_numericas})  # ← ERROR
```

### Solución

Cambiar el formato del template a **jinja2**, que usa dobles llaves `{{ variable }}` para las variables. De esta forma, las llaves simples `{10}` del código LaTeX se tratan como texto literal sin conflicto:

```python
# Antes (incorrecto — f-string por defecto):
prompt = PromptTemplate(
    template="""Analiza el siguiente código LaTeX:
{latex_code}

{format_instructions}""",
    input_variables=["latex_code"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Después (correcto — jinja2):
prompt = PromptTemplate(
    template="""Analiza el siguiente código LaTeX:
{{ latex_code }}

{{ format_instructions }}""",
    input_variables=["latex_code"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
    template_format="jinja2",
)
```

### Puntos Clave

- Las variables cambian de `{variable}` a `{{ variable }}` (dobles llaves con espacios).
- Se agrega explícitamente `template_format="jinja2"` al constructor de `PromptTemplate`.
- Esto aplica a **cualquier** `PromptTemplate` que reciba contenido con llaves literales (LaTeX, JSON crudo, código fuente con diccionarios, etc.), no solo LaTeX con `siunitx`.

> **Archivo afectado:** `agent_eda.py`
