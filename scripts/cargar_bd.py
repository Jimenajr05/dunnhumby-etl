
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
from getpass import getpass
from urllib.parse import quote_plus

# Ruta de la carpeta donde están los 8 archivos CSV
carpeta = Path(__file__).resolve().parent.parent / "database"

# Configuración de PostgreSQL
usuario = "postgres"
contrasena = quote_plus(getpass("Contraseña de PostgreSQL: "))
base_datos = "dunnhumby_etl"

engine = create_engine(
    f"postgresql+psycopg2://{usuario}:{contrasena}"
    f"@localhost:5432/{base_datos}"
)

# Buscar los archivos CSV
archivos = sorted(carpeta.glob("*.csv"))

if len(archivos) != 8:
    raise ValueError(
        f"Se esperaban 8 archivos CSV y se encontraron {len(archivos)}"
    )

# Cargar los archivos en PostgreSQL
for archivo in archivos:
    tabla = archivo.stem

    print(f"\nProcesando: {tabla}")

    primera_parte = True
    total = 0

    for bloque in pd.read_csv(archivo, chunksize=10000):
        bloque.to_sql(
            tabla,
            engine,
            if_exists="replace" if primera_parte else "append",
            index=False
        )

        primera_parte = False
        total += len(bloque)

        print(f"Registros cargados: {total}")

    print(f"Finalizado: {tabla}")

print("\nProceso terminado")