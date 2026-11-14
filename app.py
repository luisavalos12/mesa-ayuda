import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   abort, session, flash)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "solo-para-desarrollo")
DB = "tickets.db"
ESTADOS = ["Abierto", "En proceso", "Resuelto", "Cerrado"]
CATEGORIAS = ["Hardware", "Software", "Red", "Cuentas y accesos", "Otro"]
PRIORIDADES = ["Baja", "Media", "Alta"]
DEPARTAMENTOS = ["Ventas", "Contabilidad", "Recursos Humanos", "Operaciones", "TI", "Otro"]


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
SLA_HORAS = {"Alta": 8, "Media": 24, "Baja": 72}

def limite_sla(ticket):
    creado = datetime.strptime(ticket["creado"], "%Y-%m-%d %H:%M")
    return creado + timedelta(hours=SLA_HORAS[ticket["prioridad"]])

def esta_vencido(ticket):
    if ticket["estado"] in ("Resuelto", "Cerrado"):
        return False
    return datetime.now() > limite_sla(ticket)



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
        con.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        columnas = [c["name"] for c in con.execute("PRAGMA table_info(tickets)")]
        if "asignado" not in columnas:
            con.execute("ALTER TABLE tickets ADD COLUMN asignado TEXT NOT NULL DEFAULT 'Sin asignar'")
    columnas_usuarios = [c["name"] for c in con.execute("PRAGMA table_info(usuarios)")]
    if "rol" not in columnas_usuarios:
        con.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'tecnico'")
    if "departamento" not in columnas_usuarios:
        con.execute("ALTER TABLE usuarios ADD COLUMN departamento TEXT NOT NULL DEFAULT 'TI'")


def login_requerido(vista):
    """Si no hay sesión iniciada, manda al login."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", siguiente=request.path))
        return vista(*args, **kwargs)
    return envoltura


def lista_tecnicos():
    with conectar() as con:
        filas = con.execute("SELECT nombre FROM usuarios ORDER BY nombre").fetchall()
    return ["Sin asignar"] + [f["nombre"] for f in filas]

crear_tabla()



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with conectar() as con:
            u = con.execute(
                "SELECT * FROM usuarios WHERE usuario = ?", (request.form["usuario"],)
            ).fetchone()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session["usuario_id"] = u["id"]
            session["nombre"] = u["nombre"]
            session["rol"] = u["rol"]
            session["departamento"] = u["departamento"]

            siguiente = request.args.get("siguiente", "")
            # Solo redirige a rutas internas de la app
            if not siguiente.startswith("/") or siguiente.startswith("//"):
                siguiente = url_for("inicio")
            return redirect(siguiente)
        flash("Usuario o contraseña incorrectos.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_requerido
def inicio():
    if session.get("rol") == "usuario":
     return redirect(url_for("mis_tickets"))
    estado = request.args.get("estado", "")
    prioridad = request.args.get("prioridad", "")
    categoria = request.args.get("categoria", "")
    q = request.args.get("q", "").strip()
    orden = request.args.get("orden", "fecha")
    if orden not in ("fecha", "prioridad"):
        orden = "fecha"

    condiciones = []
    parametros = []
    if estado in ESTADOS:
        condiciones.append("estado = ?")
        parametros.append(estado)
    if prioridad in PRIORIDADES:
        condiciones.append("prioridad = ?")
        parametros.append(prioridad)
    if categoria in CATEGORIAS:
        condiciones.append("categoria = ?")
        parametros.append(categoria)
    if q:
        condiciones.append("(titulo LIKE ? OR descripcion LIKE ? OR usuario LIKE ?)")
        parametros.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql = "SELECT * FROM tickets"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    if orden == "prioridad":
        sql += " ORDER BY CASE prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, id DESC"
    else:
        sql += " ORDER BY id DESC"

    with conectar() as con:
     tickets = con.execute(sql, parametros).fetchall()
     tickets = [dict(fila) for fila in tickets]
     for t in tickets:
         t["limite"] = limite_sla(t).strftime("%Y-%m-%d %H:%M")
         t["vencido"] = esta_vencido(t)
     total_vencidos = sum(1 for t in tickets if t["vencido"])

     filas_estado = con.execute("SELECT estado, COUNT(*) AS n FROM tickets GROUP BY estado").fetchall()
     filas_prioridad = con.execute("SELECT prioridad, COUNT(*) AS n FROM tickets GROUP BY prioridad").fetchall()
     totales_estado = {e: 0 for e in ESTADOS}
    for f in filas_estado:
     totales_estado[f["estado"]] = f["n"]
     totales_prioridad = {p: 0 for p in PRIORIDADES}
    for f in filas_prioridad:
        totales_prioridad[f["prioridad"]] = f["n"]
    return render_template(

        "index.html",
        tickets=tickets,
        estados=ESTADOS,
        prioridades=PRIORIDADES,
        categorias=CATEGORIAS,
        estado=estado,
        prioridad=prioridad,
        categoria=categoria,
        q=q,
        orden=orden,
        totales_estado=totales_estado,
        totales_prioridad=totales_prioridad,
        total=sum(totales_estado.values()),
        total_vencidos=total_vencidos,

    )



@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    # Público: cualquier usuario puede reportar un problema
    if request.method == "POST":
     titulo = request.form.get("titulo", "").strip()
     descripcion = request.form.get("descripcion", "").strip()
     usuario = request.form.get("usuario", "").strip()
     if session.get("rol") == "usuario":
        usuario = session["nombre"]
     categoria = request.form.get("categoria", "")
     prioridad = request.form.get("prioridad", "")
     if not titulo or not descripcion or not usuario:
        flash("Faltan datos: título, descripción y usuario son obligatorios.")
        return redirect(url_for("nuevo"))
     if categoria not in CATEGORIAS or prioridad not in PRIORIDADES:
        flash("Categoría o prioridad no válida.")
        return redirect(url_for("nuevo"))
     with conectar() as con:
            cur = con.execute(
                "INSERT INTO tickets (titulo, descripcion, usuario, categoria, prioridad, creado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (titulo, descripcion, usuario, categoria, prioridad, ahora()),

            )
            nuevo_id = cur.lastrowid
     if "usuario_id" in session:
        return redirect(url_for("inicio"))
     flash(f"Tu ticket MAT-{nuevo_id:03d} fue registrado. Un técnico lo revisará pronto.")
     return redirect(url_for("nuevo"))
    return render_template("nuevo.html")



@app.route("/ticket/<int:ticket_id>")
@login_requerido
def detalle(ticket_id):
    with conectar() as con:
        ticket = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            abort(404)
        if session.get("rol") == "usuario" and ticket["usuario"] != session["nombre"]:
            abort(403)
        comentarios = con.execute(
            "SELECT * FROM comentarios WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
    return render_template(
        "detalle.html",
        ticket=ticket,
        comentarios=comentarios,
        estados=ESTADOS,
        tecnicos=lista_tecnicos(),
    )


@app.route("/ticket/<int:ticket_id>/actualizar", methods=["POST"])
@login_requerido
def actualizar(ticket_id):
    if session.get("rol") != "tecnico":
        abort(403)
    estado = request.form.get("estado", "")
    asignado = request.form.get("asignado", "")
    with conectar() as con:
        anterior = con.execute(
            "SELECT estado, asignado FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if anterior is None:
            abort(404)
        if estado not in ESTADOS or asignado not in lista_tecnicos():
            flash("Estado o técnico no válido.")
            return redirect(url_for("detalle", ticket_id=ticket_id))                     
        con.execute(
            "UPDATE tickets SET estado = ?, asignado = ? WHERE id = ?",
            (estado, asignado, ticket_id),
        )
        cambios = []
        if anterior["estado"] != estado:
            cambios.append(f"Estado: {anterior['estado']} → {estado}")
        if anterior["asignado"] != asignado:
            cambios.append(f"Asignado a: {asignado}")
        if cambios:
            con.execute(
                "INSERT INTO comentarios (ticket_id, autor, texto, creado) VALUES (?, ?, ?, ?)",
                (ticket_id, f"Sistema ({session['nombre']})", " | ".join(cambios), ahora()),
            )
    return redirect(url_for("detalle", ticket_id=ticket_id))
@app.route("/ticket/<int:ticket_id>/editar", methods=["GET", "POST"])
@login_requerido
def editar(ticket_id):
    if session.get("rol") != "tecnico":
        abort(403)
    with conectar() as con:
        ticket = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            abort(404)
        if request.method == "POST":
            titulo = request.form.get("titulo", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            categoria = request.form.get("categoria", "")
            prioridad = request.form.get("prioridad", "")
            if not titulo or not descripcion:
                flash("Faltan datos: título y descripción son obligatorios.")
                return redirect(url_for("editar", ticket_id=ticket_id))
            if categoria not in CATEGORIAS or prioridad not in PRIORIDADES:
                flash("Categoría o prioridad no válida.")
                return redirect(url_for("editar", ticket_id=ticket_id))
            con.execute(
                "UPDATE tickets SET titulo = ?, descripcion = ?, categoria = ?, prioridad = ? WHERE id = ?",
                (titulo, descripcion, categoria, prioridad, ticket_id),
            )
            return redirect(url_for("detalle", ticket_id=ticket_id))
        return render_template(
            "editar.html",
            ticket=ticket,
            categorias=CATEGORIAS,
            prioridades=PRIORIDADES,
        )

@app.route("/ticket/<int:ticket_id>/comentar", methods=["POST"])
@login_requerido
def comentar(ticket_id):
    texto = request.form.get("texto", "").strip()
    if not texto:
        flash("El comentario no puede estar vacío.")
        return redirect(url_for("detalle", ticket_id=ticket_id))
    with conectar() as con:
        existe = con.execute(
            "SELECT id FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if existe is None:
            abort(404)
        con.execute(
            "INSERT INTO comentarios (ticket_id, autor, texto, creado) VALUES (?, ?, ?, ?)",
            (ticket_id, session["nombre"], texto, ahora()),
        )
    return redirect(url_for("detalle", ticket_id=ticket_id))



@app.route("/ticket/<int:ticket_id>/eliminar", methods=["POST"])
@login_requerido
def eliminar(ticket_id):
    if session.get("rol") != "tecnico":
        abort(403)
    with conectar() as con:
        ticket = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            abort(404)
        con.execute("DELETE FROM comentarios WHERE ticket_id = ?", (ticket_id,))
        con.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    flash("Ticket eliminado.")
    return redirect(url_for("inicio"))
@app.route("/registro", methods=["GET", "POST"])
@login_requerido
def registro():
    if session.get("rol") != "tecnico":
        abort(403)
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")
        rol = request.form.get("rol", "tecnico")
        departamento = request.form.get("departamento", "TI")

        if not nombre or not usuario or not password:
            flash("Faltan datos: nombre, usuario y contraseña son obligatorios.")
            return redirect(url_for("registro"))
        if rol not in ("tecnico", "usuario") or departamento not in DEPARTAMENTOS:
           flash("Rol o departamento no válido.")
           return redirect(url_for("registro"))

        with conectar() as con:
            existe = con.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
            if existe is not None:
                flash("Ese usuario ya existe.")
                return redirect(url_for("registro"))
            con.execute(
                "INSERT INTO usuarios (usuario, nombre, password_hash, rol, departamento) VALUES (?, ?, ?, ?, ?)",
                (usuario, nombre, generate_password_hash(password), rol, departamento),
            )
        flash("Técnico registrado.")
        return redirect(url_for("inicio"))
    return render_template("registro.html", departamentos=DEPARTAMENTOS)
@app.route("/mis_tickets")
@login_requerido
def mis_tickets():
    with conectar() as con:
        filas = con.execute("SELECT * FROM tickets WHERE usuario = ? ORDER BY id DESC", (session["nombre"],)).fetchall()
    tickets = [dict(f) for f in filas]
    for t in tickets:
        t["limite"] = limite_sla(t)
        t["vencido"] = esta_vencido(t)
    return render_template("mis_tickets.html", tickets=tickets)
if __name__ == "__main__":
    app.run(debug=True)