import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort

app = Flask(__name__)
DB = "tickets.db"
ESTADOS = ["Abierto", "En proceso", "Resuelto", "Cerrado"]
TECNICOS = ["Sin asignar", "Luis", "Técnico 2"]


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def crear_tabla():
    with conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                usuario TEXT NOT NULL,
                categoria TEXT NOT NULL,
                prioridad TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Abierto',
                asignado TEXT NOT NULL DEFAULT 'Sin asignar',
                creado TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                autor TEXT NOT NULL,
                texto TEXT NOT NULL,
                creado TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        """)
        # Si la tabla ya existía (Paso 2), le agregamos la columna nueva
        columnas = [c["name"] for c in con.execute("PRAGMA table_info(tickets)")]
        if "asignado" not in columnas:
            con.execute("ALTER TABLE tickets ADD COLUMN asignado TEXT NOT NULL DEFAULT 'Sin asignar'")


@app.route("/")
def inicio():
    with conectar() as con:
        tickets = con.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()
    return render_template("index.html", tickets=tickets)


@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        with conectar() as con:
            con.execute(
                "INSERT INTO tickets (titulo, descripcion, usuario, categoria, prioridad, creado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.form["titulo"],
                    request.form["descripcion"],
                    request.form["usuario"],
                    request.form["categoria"],
                    request.form["prioridad"],
                    ahora(),
                ),
            )
        return redirect(url_for("inicio"))
    return render_template("nuevo.html")


@app.route("/ticket/<int:ticket_id>")
def detalle(ticket_id):
    with conectar() as con:
        ticket = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            abort(404)
        comentarios = con.execute(
            "SELECT * FROM comentarios WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
    return render_template(
        "detalle.html",
        ticket=ticket,
        comentarios=comentarios,
        estados=ESTADOS,
        tecnicos=TECNICOS,
    )


@app.route("/ticket/<int:ticket_id>/actualizar", methods=["POST"])
def actualizar(ticket_id):
    estado = request.form["estado"]
    asignado = request.form["asignado"]
    with conectar() as con:
        anterior = con.execute(
            "SELECT estado, asignado FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if anterior is None:
            abort(404)
        con.execute(
            "UPDATE tickets SET estado = ?, asignado = ? WHERE id = ?",
            (estado, asignado, ticket_id),
        )
        # Bitácora automática de cambios
        cambios = []
        if anterior["estado"] != estado:
            cambios.append(f"Estado: {anterior['estado']} → {estado}")
        if anterior["asignado"] != asignado:
            cambios.append(f"Asignado a: {asignado}")
        if cambios:
            con.execute(
                "INSERT INTO comentarios (ticket_id, autor, texto, creado) VALUES (?, ?, ?, ?)",
                (ticket_id, "Sistema", " | ".join(cambios), ahora()),
            )
    return redirect(url_for("detalle", ticket_id=ticket_id))


@app.route("/ticket/<int:ticket_id>/comentar", methods=["POST"])
def comentar(ticket_id):
    with conectar() as con:
        con.execute(
            "INSERT INTO comentarios (ticket_id, autor, texto, creado) VALUES (?, ?, ?, ?)",
            (ticket_id, request.form["autor"], request.form["texto"], ahora()),
        )
    return redirect(url_for("detalle", ticket_id=ticket_id))


if __name__ == "__main__":
    crear_tabla()
    app.run(debug=True)