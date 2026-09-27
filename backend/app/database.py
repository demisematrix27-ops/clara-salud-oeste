import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def obtener_conexion():
    if not DATABASE_URL:
        raise ValueError(
            "No se encontró DATABASE_URL en el archivo .env"
        )

    return psycopg2.connect(DATABASE_URL)
