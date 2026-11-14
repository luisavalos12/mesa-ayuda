import sqlite3
con = sqlite3.connect("tickets.db")
con.execute("UPDATE usuarios SET rol = 'admin' WHERE nombre = 'Luis Avalos'")
con.commit()
con.close()
print("Luis ya es maestro")
