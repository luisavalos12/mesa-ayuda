import sqlite3
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import conectar, crear_tabla

crear_tabla()
usuario = input("Usuario (para iniciar sesión): ").strip()
nombre = input("Nombre que se mostrará: ").strip()
password = getpass("Contraseña (no se ve al escribir): ")

with conectar() as con:
    try:
        con.execute(
            "INSERT INTO usuarios (usuario, nombre, password_hash) VALUES (?, ?, ?)",
            (usuario, nombre, generate_password_hash(password)),
        )
        print(f"Técnico {nombre} creado.")
    except sqlite3.IntegrityError:
        print("Ese usuario ya existe.")