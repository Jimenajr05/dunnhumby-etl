from pathlib import Path
import csv
import gzip
import getpass
import shutil
import snowflake.connector

# ======================================
# CONFIGURACIÓN
# ======================================

PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_CSV = PROYECTO / "database"

ACCOUNT = "RHBBOWX-AC33692"
DATABASE = "DUNNHUMBY_ETL"
SCHEMA = "PUBLIC"
WAREHOUSE = "SNOWFLAKE_LEARNING_WH"
STAGE = "STAGE_DUNNHUMBY"

ARCHIVOS = [
    "campaign_desc.csv",
    "campaign_table.csv",
    "coupon.csv",
    "coupon_redempt.csv",
    "hh_demographic.csv",
    "product.csv",
    "transaction_data.csv",
]

# ======================================
# FUNCIONES
# ======================================

def comprimir(origen):
    destino = origen.with_suffix(origen.suffix + ".gz")

    if not destino.exists():
        print(f"Comprimiendo {origen.name}...")

        with open(origen, "rb") as entrada:
            with gzip.open(destino, "wb") as salida:
                shutil.copyfileobj(entrada, salida)

    return destino


def obtener_columnas(archivo):
    with open(archivo, "r", encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        return next(lector)


# ======================================
# CONEXIÓN
# ======================================

usuario = input("Usuario de Snowflake: ").strip()
contrasena = getpass.getpass("Contraseña de Snowflake: ")

conexion = snowflake.connector.connect(
    account=ACCOUNT,
    user=usuario,
    password=contrasena,
    role="SYSADMIN",
    warehouse=WAREHOUSE,
    database=DATABASE,
    schema=SCHEMA
)

cursor = conexion.cursor()

try:
    cursor.execute("""
        create stage if not exists STAGE_DUNNHUMBY
    """)

    cursor.execute("""
        create file format if not exists FORMATO_DUNNHUMBY_CSV
        type = CSV
        field_delimiter = ','
        skip_header = 1
        field_optionally_enclosed_by = '"'
        null_if = ('', 'NULL')
        compression = GZIP
    """)

    for nombre_archivo in ARCHIVOS:
        archivo = CARPETA_CSV / nombre_archivo

        if not archivo.exists():
            print(f"No se encontró {nombre_archivo}")
            continue

        tabla = archivo.stem.upper()

        # No modificar tablas existentes
        cursor.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = %s and table_name = %s",
            (SCHEMA, tabla)
        )

        if cursor.fetchone()[0] > 0:
            print(f"{tabla} ya existe. Se omite.")
            continue

        print(f"\nProcesando {nombre_archivo}...")

        columnas = obtener_columnas(archivo)

        # Se crean como VARCHAR para conservar
        # los valores originales sin asumir tipos
        definiciones = ", ".join(
            f'"{col.upper()}" VARCHAR(16777216)'
            for col in columnas
        )

        cursor.execute(
            f"create table {tabla} ({definiciones})"
        )

        comprimido = comprimir(archivo)

        cursor.execute(
            f"PUT 'file://{comprimido.as_posix()}' "
            f"@{STAGE} "
            "AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
        )

        cursor.execute(f"""
            copy into {tabla}
            from @{STAGE}/{comprimido.name}
            file_format = (
                format_name = FORMATO_DUNNHUMBY_CSV
            )
            on_error = ABORT_STATEMENT
        """)

        cursor.execute(f"select count(*) from {tabla}")
        cantidad = cursor.fetchone()[0]

        print(f"{tabla}: {cantidad} registros cargados.")

    print("\nProceso finalizado.")

finally:
    cursor.close()
    conexion.close()
