import sqlite3

usuario = input("Usuario que será admin: ").strip()

con = sqlite3.connect("tickets.db")
cur = con.execute("UPDATE usuarios SET rol = 'admin' WHERE usuario = ?", (usuario,))
con.commit()
con.close()

if cur.rowcount:
    print(f"{usuario} ya es maestro (admin).")
else:
    print("No existe ese usuario. Créalo primero con crear_usuario.py")