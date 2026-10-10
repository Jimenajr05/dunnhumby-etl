from pathlib import Path
import getpass
import gzip
import shutil
import snowflake.connector

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================

proyecto = Path(__file__).resolve().parent.parent
archivo = proyecto / "database" / "causal_data.csv"
comprimido = proyecto / "database" / "causal_data.csv.gz"

ACCOUNT = "RHBBOWX-AC33692"
WAREHOUSE = "SNOWFLAKE_LEARNING_WH"
DATABASE = "DUNNHUMBY_ETL"
SCHEMA = "PUBLIC"
TABLA = "CAUSAL_DATA"
STAGE = "STAGE_DUNNHUMBY"

# ==========================================
# 2. VERIFICAR Y COMPRIMIR EL CSV
# ==========================================

if not archivo.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {archivo}"
    )

if not comprimido.exists():
    print("Comprimiendo causal_data.csv...")

    with open(archivo, "rb") as origen:
        with gzip.open(comprimido, "wb") as destino:
            shutil.copyfileobj(origen, destino)

    print("Archivo comprimido correctamente.")
else:
    print("El archivo comprimido ya existe.")

print(
    "Tamaño comprimido:",
    round(comprimido.stat().st_size / 1024**2, 2),
    "MB"
)

# ==========================================
# 3. CONECTAR CON SNOWFLAKE
# ==========================================

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
    print("\nConexión exitosa con Snowflake.")

    # ==========================================
    # 4. CREAR LA TABLA
    # ==========================================

    cursor.execute(f"""
        create table if not exists {TABLA} (
            PRODUCT_ID number,
            STORE_ID number,
            WEEK_NO number,
            DISPLAY varchar(100),
            MAILER varchar(100)
        )
    """)

    print(f"Tabla {TABLA} creada o verificada.")

    # ==========================================
    # 5. CREAR EL STAGE
    # ==========================================

    cursor.execute(f"""
        create stage if not exists {STAGE}
    """)

    print("Stage creado o verificado.")

    # ==========================================
    # 6. SUBIR EL ARCHIVO COMPRIMIDO
    # ==========================================

    print("\nSubiendo archivo a Snowflake...")

    ruta = comprimido.as_posix()

    cursor.execute(
        f"PUT 'file://{ruta}' "
        f"@{STAGE} "
        "AUTO_COMPRESS=FALSE "
        "OVERWRITE=FALSE"
    )

    print("Archivo disponible en el stage.")

    # ==========================================
    # 7. CONFIGURAR EL FORMATO CSV
    # ==========================================

    cursor.execute("""
        create file format if not exists FORMATO_DUNNHUMBY_CSV
        type = CSV
        field_delimiter = ','
        skip_header = 1
        field_optionally_enclosed_by = '"'
        null_if = ('', 'NULL')
        compression = GZIP
    """)

    print("Formato CSV configurado.")

    # ==========================================
    # 8. CARGAR LOS DATOS
    # ==========================================

    print("\nCargando registros en CAUSAL_DATA...")

    cursor.execute(f"""
        copy into {TABLA}
        from @{STAGE}/causal_data.csv.gz
        file_format = (
            format_name = FORMATO_DUNNHUMBY_CSV
        )
        on_error = ABORT_STATEMENT
    """)

    resultados = cursor.fetchall()

    print("\nResultado de la carga:")

    for resultado in resultados:
        print(resultado)

    # ==========================================
    # 9. COMPROBAR LA CANTIDAD DE REGISTROS
    # ==========================================

    cursor.execute(f"""
        select count(*) from {TABLA}
    """)

    cantidad = cursor.fetchone()[0]

    print("\n==================================")
    print("CARGA FINALIZADA")
    print("Tabla:", TABLA)
    print("Total de registros:", cantidad)
    print("==================================")

finally:
    cursor.close()
    conexion.close()
    print("\nConexión cerrada.")