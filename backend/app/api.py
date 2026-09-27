from .services.gemini_service import (
    analizar_sintomas_con_gemini
)

from fastapi.middleware.cors import CORSMiddleware

import re
import unicodedata

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from .database import obtener_conexion

app = FastAPI(
    title="Estimador de Copago",
    description="API para clínicas privadas de La Chorrera",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clara-salud-oeste.netlify.app/",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
 )



class SintomasRequest(BaseModel):
    sintomas: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Descripción de los síntomas del paciente"
    )


class RecomendacionRequest(BaseModel):
    sintomas: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Síntomas escritos por el paciente"
    )


class RecomendacionCopagoRequest(BaseModel):
    sintomas: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Síntomas escritos por el paciente"
    )

    plan_id: int = Field(
        ...,
        description="ID del plan de seguro seleccionado"
    )


class GeminiTriageRequest(BaseModel):
    sintomas: str = Field(
        ...,
        min_length=5,
        max_length=1000
    )


def normalizar_texto(texto: str) -> str:
    """
    Convierte el texto a minúsculas y elimina acentos
    para facilitar la comparación de palabras.
    """
    texto = texto.lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


def contiene_alguna_palabra(
    texto: str,
    palabras: list[str]
) -> bool:
    """
    Verifica si el texto contiene alguna palabra o frase
    de la lista recibida.
    """
    return any(palabra in texto for palabra in palabras)


@app.get("/")
def inicio():
    return {
        "mensaje": "API del estimador de copago funcionando"
    }


@app.get("/hospitales")
def obtener_hospitales():
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                id,
                nombre,
                ubicacion,
                distrito,
                provincia,
                telefono,
                whatsapp,
                servicios,
                activo,
                estado_dato
            FROM hospitales
            WHERE activo = TRUE
            ORDER BY nombre;
        """)

        columnas = [descripcion[0] for descripcion in cursor.description]
        resultados = cursor.fetchall()

        hospitales = [
            dict(zip(columnas, fila))
            for fila in resultados
        ]

        return hospitales

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar hospitales: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.get("/especialidades")
def obtener_especialidades():
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                id,
                nombre,
                descripcion
            FROM especialidades
            WHERE activa = TRUE
            ORDER BY nombre;
        """)

        columnas = [descripcion[0] for descripcion in cursor.description]
        resultados = cursor.fetchall()

        especialidades = [
            dict(zip(columnas, fila))
            for fila in resultados
        ]

        return especialidades

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar especialidades: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.get("/planes")
def obtener_planes():
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                id,
                nombre,
                descripcion,
                tipo,
                es_demo
            FROM planes_seguro
            WHERE activo = TRUE
            ORDER BY nombre;
        """)

        columnas = [descripcion[0] for descripcion in cursor.description]
        resultados = cursor.fetchall()

        planes = [
            dict(zip(columnas, fila))
            for fila in resultados
        ]

        return planes

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar planes: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.get("/estimacion")
def calcular_estimacion(
    hospital_id: int,
    especialidad_id: int,
    plan_id: int
):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                h.nombre AS hospital,
                e.nombre AS especialidad,
                p.nombre AS plan,
                t.precio_consulta,
                c.porcentaje_cobertura,
                c.copago_fijo,
                c.deducible_pendiente,
                t.es_demo AS tarifa_demo,
                c.es_demo AS cobertura_demo,
                hp.confirmado
            FROM hospitales h
            JOIN tarifas t
                ON t.hospital_id = h.id
            JOIN especialidades e
                ON e.id = t.especialidad_id
            JOIN coberturas c
                ON c.especialidad_id = e.id
            JOIN planes_seguro p
                ON p.id = c.plan_id
            JOIN hospital_plan hp
                ON hp.hospital_id = h.id
                AND hp.plan_id = p.id
            WHERE h.id = %s
              AND e.id = %s
              AND p.id = %s
            ORDER BY t.fecha_actualizacion DESC
            LIMIT 1;
        """, (hospital_id, especialidad_id, plan_id))

        resultado = cursor.fetchone()

        if not resultado:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No existe una tarifa, cobertura o relación "
                    "para los datos enviados"
                )
            )

        (
            hospital,
            especialidad,
            plan,
            precio_consulta,
            porcentaje_cobertura,
            copago_fijo,
            deducible_pendiente,
            tarifa_demo,
            cobertura_demo,
            confirmado
        ) = resultado

        if precio_consulta is None:
            raise HTTPException(
                status_code=404,
                detail="La tarifa de consulta aún no está disponible"
            )

        if porcentaje_cobertura is None:
            raise HTTPException(
                status_code=404,
                detail="La cobertura aún no está disponible"
            )

        parte_no_cubierta = precio_consulta * (
            1 - porcentaje_cobertura / 100
        )

        copago_estimado = (
            parte_no_cubierta
            + copago_fijo
            + deducible_pendiente
        )

        es_demo = tarifa_demo or cobertura_demo

        return {
            "hospital": hospital,
            "especialidad": especialidad,
            "plan": plan,
            "precio_consulta": float(precio_consulta),
            "porcentaje_cobertura": float(porcentaje_cobertura),
            "copago_fijo": float(copago_fijo),
            "deducible_pendiente": float(deducible_pendiente),
            "copago_estimado": round(float(copago_estimado), 2),
            "es_demo": es_demo,
            "relacion_confirmada": confirmado,
            "mensaje": (
                "Resultado de demostración. "
                "Confirme la tarifa y cobertura."
                if es_demo
                else
                "Confirme la vigencia de la tarifa y cobertura."
            )
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular estimación: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.post("/triage")
def sugerir_especialidad(datos: SintomasRequest):
    texto = normalizar_texto(datos.sintomas)

    if not texto:
        raise HTTPException(
            status_code=400,
            detail="Debe escribir los síntomas"
        )

    # Estas reglas se evalúan antes que Gemini y antes de
    # cualquier especialidad. La dificultad respiratoria
    # siempre tiene prioridad sobre síntomas como espalda.
    palabras_alarma = {
        "dolor de pecho": "Dolor en el pecho",
        "dolor pecho": "Dolor en el pecho",
        "dificultad para respirar": "Dificultad para respirar",
        "dificultad al respirar": "Dificultad para respirar",
        "me cuesta respirar": "Dificultad para respirar",
        "cuesta respirar": "Dificultad para respirar",
        "no puedo respirar": "Dificultad para respirar",
        "me falta el aire": "Falta de aire",
        "falta de aire": "Falta de aire",
        "respirar con dificultad": "Dificultad para respirar",
        "respiracion dificultosa": "Dificultad para respirar",
        "desmayo": "Pérdida del conocimiento",
        "me desmaye": "Pérdida del conocimiento",
        "perdi el conocimiento": "Pérdida del conocimiento",
        "convulsion": "Convulsiones",
        "convulsiones": "Convulsiones",
        "sangrado abundante": "Sangrado abundante",
        "cara torcida": "Posible alteración neurológica",
        "dificultad para hablar": "Posible alteración neurológica",
        "habla mal": "Posible alteración neurológica",
        "debilidad de un lado": "Posible alteración neurológica",
        "accidente grave": "Accidente grave",
        "reaccion alergica grave": "Reacción alérgica grave",
        "reaccion alergica": "Posible reacción alérgica"
    }

    senales_alarma = []
    for palabra, descripcion in palabras_alarma.items():
        if palabra in texto and descripcion not in senales_alarma:
            senales_alarma.append(descripcion)

    if senales_alarma:
        return {
            "especialidad_sugerida": "Medicina general",
            "nivel_confianza": "alto",
            "sintomas_detectados": [],
            "senales_alarma": senales_alarma,
            "prioridad": "urgente",
            "posible_urgencia": True,
            "explicacion": (
                "Los síntomas descritos incluyen posibles señales "
                "de alarma. Se recomienda buscar atención médica "
                "inmediata en lugar de seleccionar una clínica "
                "únicamente por el costo."
            ),
            "mensaje": (
                "Se detectaron posibles señales de alarma. "
                "Busca atención médica inmediata."
            )
        }

    reglas_especialidad = [
        {
            "especialidad": "Cardiología",
            "palabras": ["palpitaciones", "corazon", "presion en el pecho", "latidos irregulares"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con el corazón. Una evaluación médica puede determinar si se necesita atención especializada."
        },
        {
            "especialidad": "Ortopedia",
            "palabras": ["espalda", "rodilla", "hueso", "articulacion", "musculo", "fractura", "esguince", "dolor muscular", "dolor lumbar"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con huesos, músculos o articulaciones."
        },
        {
            "especialidad": "Dermatología",
            "palabras": ["piel", "sarpullido", "erupcion", "manchas", "acne", "picazon", "verruga"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con la piel."
        },
        {
            "especialidad": "Pediatría",
            "palabras": ["bebe", "nino", "nina", "hijo", "hija", "infante"],
            "explicacion": "La consulta parece estar relacionada con un niño o una niña."
        },
        {
            "especialidad": "Ginecología y obstetricia",
            "palabras": ["embarazo", "embarazada", "menstruacion", "periodo", "ovario", "flujo vaginal", "dolor menstrual"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con la salud ginecológica."
        },
        {
            "especialidad": "Otorrinolaringología",
            "palabras": ["oido", "garganta", "nariz", "sinusitis", "audicion", "zumbido"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con oído, nariz o garganta."
        },
        {
            "especialidad": "Odontología",
            "palabras": ["diente", "muela", "encia", "dolor dental", "caries", "boca"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con la salud bucal."
        },
        {
            "especialidad": "Urología",
            "palabras": ["orinar", "orina", "urinario", "vejiga", "prostata", "ardor al orinar"],
            "explicacion": "Los síntomas mencionados pueden relacionarse con el sistema urinario."
        }
    ]

    especialidad_sugerida = "Medicina general"
    explicacion = (
        "Los síntomas descritos no permiten identificar con suficiente "
        "claridad una especialidad específica. Medicina general es un "
        "primer punto de evaluación para revisar el cuadro completo y "
        "determinar si se necesita una referencia a otra especialidad."
    )
    nivel_confianza = "bajo"
    sintomas_detectados = []

    for regla in reglas_especialidad:
        coincidencias = [
            palabra for palabra in regla["palabras"]
            if normalizar_texto(palabra) in texto
        ]
        if coincidencias:
            especialidad_sugerida = regla["especialidad"]
            explicacion = regla["explicacion"]
            sintomas_detectados = coincidencias
            nivel_confianza = "medio"
            break

    return {
        "especialidad_sugerida": especialidad_sugerida,
        "nivel_confianza": nivel_confianza,
        "sintomas_detectados": sintomas_detectados,
        "senales_alarma": [],
        "prioridad": "normal",
        "posible_urgencia": False,
        "explicacion": explicacion,
        "mensaje": (
            "Esta sugerencia es orientativa y no constituye "
            "un diagnóstico médico."
        )
    }

def analizar_sintomas_inteligente(
    sintomas: str
):
    """
    Analiza los síntomas usando este orden:

    1. Reglas locales para seguridad.
    2. Gemini para interpretar el lenguaje natural.
    3. Reglas locales como respaldo si Gemini falla.
    """

    analisis_local = sugerir_especialidad(
        SintomasRequest(sintomas=sintomas)
    )

    # Las señales de alarma locales siempre tienen prioridad.
    if analisis_local["prioridad"] == "urgente":
        return {
            **analisis_local,
            "posible_urgencia": True,
            "fuente": "reglas_locales_seguridad",
            "modelo": None
        }

    try:
        resultado_gemini = analizar_sintomas_con_gemini(
            sintomas
        )

        prioridad = (
            "urgente"
            if resultado_gemini.posible_urgencia
            else "normal"
        )

        # Si Gemini identifica una posible urgencia,
        # el endpoint principal podrá detener las recomendaciones.
        if resultado_gemini.posible_urgencia:
            mensaje = (
                "Se detectaron posibles señales de alarma. "
                "Busca atención médica inmediata. "
                "Esta herramienta no sustituye una evaluación profesional."
            )
        else:
            mensaje = (
                "La especialidad sugerida es orientativa "
                "y no constituye un diagnóstico médico."
            )

        return {
            "especialidad_sugerida": (
                resultado_gemini.especialidad_sugerida
            ),
            "nivel_confianza": (
                resultado_gemini.nivel_confianza
            ),
            "sintomas_detectados": (
                resultado_gemini.sintomas_detectados
            ),
            "senales_alarma": [],
            "prioridad": prioridad,
            "posible_urgencia": (
                resultado_gemini.posible_urgencia
            ),
            "explicacion": (
                resultado_gemini.explicacion.strip()
            ),
            "mensaje": mensaje,
            "fuente": "gemini",
            "modelo": "gemini-2.5-flash"
        }

    except Exception as error:
        print(
            "Gemini no respondió. "
            "Se usará el análisis local:",
            repr(error)
        )

        especialidad_local = (
            analisis_local["especialidad_sugerida"]
        )

        if especialidad_local == "Medicina general":
            explicacion_respaldo = (
                "Los síntomas descritos no permiten identificar "
                "con suficiente claridad una especialidad específica. "
                "Medicina general es un primer punto de evaluación "
                "para revisar el cuadro completo y determinar si "
                "se necesita una referencia a otra especialidad. "
                "Esta orientación no constituye un diagnóstico médico."
            )
        else:
            explicacion_respaldo = (
                analisis_local.get(
                    "explicacion",
                    "La sugerencia es orientativa y no constituye "
                    "un diagnóstico médico."
                )
            )

        return {
            **analisis_local,
            "posible_urgencia": False,
            "explicacion": explicacion_respaldo,
            "fuente": "reglas_locales_fallback",
            "modelo": None,
            "mensaje": (
                "Gemini no está disponible temporalmente. "
                "Se utilizó un análisis local de respaldo. "
                "La sugerencia es orientativa y no constituye "
                "un diagnóstico médico."
            )
        }


@app.post("/recomendaciones")
def obtener_recomendaciones(datos: RecomendacionRequest):
    """
    Analiza los síntomas, sugiere una especialidad
    y busca clínicas privadas relacionadas.
    """

    # Reutiliza el análisis que ya construimos
    analisis = analizar_sintomas_inteligente(
        datos.sintomas
    )

    especialidad_nombre = analisis["especialidad_sugerida"]

    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Busca la especialidad sugerida en Supabase
        cursor.execute("""
            SELECT id, nombre
            FROM especialidades
            WHERE LOWER(nombre) = LOWER(%s)
              AND activa = TRUE
            LIMIT 1;
        """, (especialidad_nombre,))

        especialidad = cursor.fetchone()

        if not especialidad:
            return {
                "analisis": analisis,
                "clinicas": [],
                "mensaje": (
                    "La especialidad sugerida todavía no tiene "
                    "datos registrados en el sistema."
                )
            }

        especialidad_id, nombre_especialidad = especialidad

        # Busca clínicas que tengan tarifas registradas
        # para esa especialidad
        cursor.execute("""
            SELECT DISTINCT
                h.id,
                h.nombre,
                h.ubicacion,
                h.telefono,
                h.whatsapp,
                h.servicios,
                h.estado_dato,
                t.precio_consulta,
                t.es_demo
            FROM hospitales h
            INNER JOIN tarifas t
                ON t.hospital_id = h.id
            WHERE t.especialidad_id = %s
              AND h.activo = TRUE
            ORDER BY h.nombre;
        """, (especialidad_id,))

        resultados = cursor.fetchall()

        clinicas = []

        for fila in resultados:
            (
                hospital_id,
                nombre,
                ubicacion,
                telefono,
                whatsapp,
                servicios,
                estado_dato,
                precio_consulta,
                tarifa_es_demo
            ) = fila

            clinicas.append({
                "hospital_id": hospital_id,
                "nombre": nombre,
                "ubicacion": ubicacion,
                "telefono": telefono,
                "whatsapp": whatsapp,
                "servicios": servicios,
                "estado_dato": estado_dato,
                "especialidad": nombre_especialidad,
                "precio_consulta": (
                    float(precio_consulta)
                    if precio_consulta is not None
                    else None
                ),
                "tarifa_es_demo": tarifa_es_demo
            })

        return {
            "analisis": analisis,
            "especialidad_id": especialidad_id,
            "especialidad": nombre_especialidad,
            "clinicas": clinicas,
            "total_clinicas": len(clinicas),
            "mensaje": (
                "Estas opciones se basan en los datos registrados. "
                "Confirme horarios, disponibilidad y tarifas directamente "
                "con la clínica."
            )
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener recomendaciones: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.post("/recomendaciones-copago")
def obtener_recomendaciones_con_copago(
    datos: RecomendacionCopagoRequest
):
    """
    Analiza síntomas, sugiere una especialidad
    y calcula el copago estimado en cada clínica.
    """

    # 1. Analizar los síntomas con el endpoint local
    analisis = analizar_sintomas_inteligente(
        datos.sintomas
    )

    especialidad_nombre = analisis["especialidad_sugerida"]

    # 2. Si se detecta una urgencia, se informa primero
    if analisis["prioridad"] == "urgente":
        return {
            "analisis": analisis,
            "clinicas": [],
            "total_clinicas": 0,
            "mensaje": (
                "Se detectaron posibles señales de alarma. "
                "Debe buscar atención médica inmediata. "
                "No seleccione una clínica basándose únicamente "
                "en el costo."
            )
        }

    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # 3. Buscar la especialidad y el plan
        cursor.execute("""
            SELECT
                e.id,
                e.nombre,
                p.id,
                p.nombre,
                p.es_demo
            FROM especialidades e
            CROSS JOIN planes_seguro p
            WHERE LOWER(e.nombre) = LOWER(%s)
              AND e.activa = TRUE
              AND p.id = %s
              AND p.activo = TRUE
            LIMIT 1;
        """, (especialidad_nombre, datos.plan_id))

        datos_base = cursor.fetchone()

        if not datos_base:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No se encontró la especialidad o el plan "
                    "seleccionado."
                )
            )

        (
            especialidad_id,
            nombre_especialidad,
            plan_id,
            nombre_plan,
            plan_es_demo
        ) = datos_base

        # 4. Buscar clínicas, tarifas y coberturas
        cursor.execute("""
            SELECT
                h.id,
                h.nombre,
                h.ubicacion,
                h.telefono,
                h.whatsapp,
                h.servicios,
                h.estado_dato,

                t.precio_consulta,
                t.es_demo AS tarifa_es_demo,

                c.porcentaje_cobertura,
                c.copago_fijo,
                c.deducible_pendiente,
                c.es_demo AS cobertura_es_demo,
                c.requiere_autorizacion,

                hp.confirmado,
                hp.es_demo AS relacion_es_demo

            FROM hospitales h
            INNER JOIN tarifas t
                ON t.hospital_id = h.id
                AND t.especialidad_id = %s

            INNER JOIN hospital_plan hp
                ON hp.hospital_id = h.id
                AND hp.plan_id = %s

            INNER JOIN coberturas c
                ON c.plan_id = %s
                AND c.especialidad_id = %s

            WHERE h.activo = TRUE
            ORDER BY h.nombre;
        """, (
            especialidad_id,
            plan_id,
            plan_id,
            especialidad_id
        ))

        resultados = cursor.fetchall()

        clinicas = []

        for fila in resultados:
            (
                hospital_id,
                nombre_hospital,
                ubicacion,
                telefono,
                whatsapp,
                servicios,
                estado_dato,
                precio_consulta,
                tarifa_es_demo,
                porcentaje_cobertura,
                copago_fijo,
                deducible_pendiente,
                cobertura_es_demo,
                requiere_autorizacion,
                relacion_confirmada,
                relacion_es_demo
            ) = fila

            # Si falta tarifa o porcentaje, no se puede calcular
            if (
                precio_consulta is None
                or porcentaje_cobertura is None
            ):
                copago_estimado = None
            else:
                parte_no_cubierta = (
                    precio_consulta
                    * (100 - porcentaje_cobertura)
                    / 100
                )

                copago_estimado = (
                    parte_no_cubierta
                    + copago_fijo
                    + deducible_pendiente
                )

                copago_estimado = round(
                    float(copago_estimado),
                    2
                )

            resultado_es_demo = (
                tarifa_es_demo
                or cobertura_es_demo
                or relacion_es_demo
                or plan_es_demo
            )

            clinicas.append({
                "hospital_id": hospital_id,
                "nombre": nombre_hospital,
                "ubicacion": ubicacion,
                "telefono": telefono,
                "whatsapp": whatsapp,
                "servicios": servicios,
                "estado_dato": estado_dato,
                "especialidad": nombre_especialidad,
                "plan": nombre_plan,
                "precio_consulta": (
                    float(precio_consulta)
                    if precio_consulta is not None
                    else None
                ),
                "porcentaje_cobertura": (
                    float(porcentaje_cobertura)
                    if porcentaje_cobertura is not None
                    else None
                ),
                "copago_fijo": float(copago_fijo),
                "deducible_pendiente": float(
                    deducible_pendiente
                ),
                "copago_estimado": copago_estimado,
                "requiere_autorizacion": requiere_autorizacion,
                "relacion_confirmada": relacion_confirmada,
                "es_demo": resultado_es_demo
            })

        # 5. Ordenar primero los copagos calculables más bajos
        clinicas.sort(
            key=lambda clinica: (
                clinica["copago_estimado"] is None,
                clinica["copago_estimado"]
                if clinica["copago_estimado"] is not None
                else float("inf")
            )
        )

        if not clinicas:
            mensaje = (
                "No existen clínicas con tarifa y cobertura "
                "registradas para esta especialidad y plan."
            )
        else:
            mensaje = (
                "Los resultados son estimaciones. Confirme "
                "la tarifa, cobertura, disponibilidad y autorización "
                "directamente con la clínica o aseguradora."
            )

        return {
            "analisis": analisis,
            "plan_id": plan_id,
            "plan": nombre_plan,
            "especialidad_id": especialidad_id,
            "especialidad": nombre_especialidad,
            "clinicas": clinicas,
            "total_clinicas": len(clinicas),
            "mensaje": mensaje
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular recomendaciones: {error}"
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.post("/triage-gemini")
def triage_con_gemini(
    datos: GeminiTriageRequest
):
    """
    Analiza síntomas con Gemini, pero mantiene reglas locales
    como respaldo y para detectar señales de alarma.
    """

    # Primero se ejecutan las reglas locales.
    # Esto permite detectar urgencias aunque Gemini no funcione.
    analisis_local = sugerir_especialidad(
        SintomasRequest(sintomas=datos.sintomas)
    )

    # Las señales de alarma tienen prioridad.
    if analisis_local["prioridad"] == "urgente":
        return {
            "especialidad_sugerida": (
                analisis_local["especialidad_sugerida"]
            ),
            "sintomas_detectados": (
                analisis_local["sintomas_detectados"]
            ),
            "nivel_confianza": (
                analisis_local["nivel_confianza"]
            ),
            "posible_urgencia": True,
            "senales_alarma": (
                analisis_local["senales_alarma"]
            ),
            "explicacion": (
                analisis_local["explicacion"]
            ),
            "mensaje": (
                "Se detectaron posibles señales de alarma. "
                "Busca atención médica inmediata. "
                "No esperes una respuesta de la IA."
            ),
            "fuente": "reglas_locales_seguridad",
            "modelo": None
        }

    try:
        resultado = analizar_sintomas_con_gemini(
            datos.sintomas
        )

        return {
            "especialidad_sugerida": (
                resultado.especialidad_sugerida
            ),
            "sintomas_detectados": (
                resultado.sintomas_detectados
            ),
            "nivel_confianza": (
                resultado.nivel_confianza
            ),
            "posible_urgencia": (
                resultado.posible_urgencia
            ),
            "senales_alarma": [],
            "explicacion": resultado.explicacion,
            "mensaje": (
                "La especialidad sugerida es orientativa "
                "y no constituye un diagnóstico médico."
            ),
            "fuente": "gemini",
            "modelo": "gemini-2.5-flash"
        }

    except Exception as error:
        mensaje_error = str(error)

        es_error_temporal = (
            "503" in mensaje_error
            or "UNAVAILABLE" in mensaje_error
            or "high demand" in mensaje_error
        )

        if es_error_temporal:
            return {
                "especialidad_sugerida": (
                    analisis_local["especialidad_sugerida"]
                ),
                "sintomas_detectados": (
                    analisis_local["sintomas_detectados"]
                ),
                "nivel_confianza": (
                    analisis_local["nivel_confianza"]
                ),
                "posible_urgencia": False,
                "senales_alarma": [],
                "explicacion": (
                    analisis_local["explicacion"]
                ),
                "mensaje": (
                    "Gemini está temporalmente ocupado. "
                    "Se utilizó el análisis local de respaldo. "
                    "Esta sugerencia es orientativa y no constituye "
                    "un diagnóstico médico."
                ),
                "fuente": "reglas_locales_fallback",
                "modelo": None
            }

        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible comunicarse correctamente "
                "con el servicio de Gemini."
            )
        )
