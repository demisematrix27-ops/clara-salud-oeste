import json
import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field


# Buscar el .env en la carpeta principal del proyecto
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        f"No se encontró GEMINI_API_KEY en {ENV_FILE}"
    )

client = genai.Client(
    api_key=GEMINI_API_KEY
)


class ResultadoGemini(BaseModel):
    especialidad_sugerida: Literal[
        "Medicina general",
        "Cardiología",
        "Ortopedia",
        "Dermatología",
        "Pediatría",
        "Ginecología y obstetricia",
        "Otorrinolaringología",
        "Odontología",
        "Urología"
    ]

    sintomas_detectados: list[str] = Field(
        default_factory=list
    )

    nivel_confianza: Literal[
        "bajo",
        "medio",
        "alto"
    ]

    posible_urgencia: bool

    explicacion: str = Field(
        description=(
            "Explicación orientativa de 2 o 3 frases. "
            "Debe mencionar los síntomas observados, "
            "explicar por qué la especialidad seleccionada "
            "es un primer paso razonable y aclarar que "
            "no es un diagnóstico."
        )
    )


def analizar_sintomas_con_gemini(
    sintomas: str
) -> ResultadoGemini:

    prompt = f"""
Eres un clasificador orientativo para un sistema académico
de clínicas privadas en La Chorrera, Panamá Oeste.

Analiza los síntomas escritos por el usuario.

Reglas importantes:

- No realices diagnósticos.
- No recomiendes medicamentos.
- No inventes precios.
- No inventes coberturas.
- No afirmes que el paciente tiene una enfermedad.
- Selecciona únicamente una especialidad de la lista permitida.

Especialidades permitidas:

- Medicina general
- Cardiología
- Ortopedia
- Dermatología
- Pediatría
- Ginecología y obstetricia
- Otorrinolaringología
- Odontología
- Urología

Marca posible_urgencia como true si aparecen señales como:

- dolor en el pecho
- dificultad para respirar
- falta de aire
- desmayo
- convulsiones
- sangrado abundante
- debilidad repentina de un lado del cuerpo
- dificultad repentina para hablar

Si no hay suficiente información para identificar
una especialidad específica, utiliza:

- especialidad_sugerida: Medicina general
- nivel_confianza: bajo
- posible_urgencia: false

Cuando selecciones Medicina general, explica que es
un primer punto de evaluación porque permite revisar
los síntomas de manera general y determinar si el paciente
necesita ser referido a otra especialidad.

La explicación debe:

- Tener entre 2 y 3 frases.
- Basarse únicamente en los síntomas escritos.
- Mencionar los síntomas relevantes encontrados.
- Explicar por qué la especialidad es un primer paso razonable.
- Usar lenguaje sencillo y claro.
- Indicar que la sugerencia no es un diagnóstico.
- No inventar duración, intensidad, enfermedades,
  antecedentes, medicamentos ni resultados médicos.
- No afirmar que el paciente tiene una enfermedad.
- No recomendar medicamentos.
- No mencionar precios, clínicas ni coberturas.

Ejemplo para Medicina general:

"Los síntomas descritos no permiten identificar de forma
suficiente una especialidad específica. Medicina general
es un primer punto de evaluación para revisar el cuadro
completo y determinar si se necesita una referencia.
Esta orientación no constituye un diagnóstico médico."

Devuelve únicamente un objeto JSON válido.

Síntomas del usuario:
{sintomas}
"""

    response = None
    ultimo_error = None

    for intento in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": (
                        ResultadoGemini.model_json_schema()
                    )
                }
            )

            break

        except Exception as error:
            ultimo_error = error
            mensaje_error = str(error)

            error_temporal = (
                "503" in mensaje_error
                or "UNAVAILABLE" in mensaje_error
                or "high demand" in mensaje_error
            )

            if not error_temporal:
                raise

            if intento < 2:
                time.sleep(1.5 * (intento + 1))

    if response is None:
        raise RuntimeError(
            "Gemini no está disponible temporalmente."
        ) from ultimo_error

    if not response.text:
        raise ValueError(
            "Gemini no devolvió una respuesta."
        )

    try:
        resultado_json = json.loads(response.text)

    except json.JSONDecodeError as error:
        raise ValueError(
            "Gemini no devolvió JSON válido."
        ) from error

    return ResultadoGemini.model_validate(
        resultado_json
    )
