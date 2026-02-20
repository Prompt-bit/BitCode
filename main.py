from flask import Flask, render_template, redirect, session, request
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "abc123"

def get_db():
    return sqlite3.connect("users.db")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            code TEXT NOT NULL,
            is_public INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # Migration for existing databases created before description existed.
    c.execute("PRAGMA table_info(projects)")
    project_columns = [column[1] for column in c.fetchall()]
    if "description" not in project_columns:
        c.execute("ALTER TABLE projects ADD COLUMN description TEXT DEFAULT ''")

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html", username=session.get("username"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      (username, password))
            conn.commit()
        except:
            conn.close()
            return "Username already exists!"

        conn.close()
        return redirect("/login")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/profile")
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    return redirect(f"/profile/{session['username']}")


@app.route("/profile/<username>")
def public_profile(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username = ?", (username,))
    user = c.fetchone()

    if not user:
        conn.close()
        return "User not found"

    viewer_is_owner = session.get("user_id") == user[0]
    if viewer_is_owner:
        c.execute(
            "SELECT id, title, is_public, description FROM projects WHERE user_id = ?",
            (user[0],),
        )
    else:
        c.execute(
            """
            SELECT id, title, is_public, description
            FROM projects
            WHERE user_id = ? AND is_public = 1
            """,
            (user[0],),
        )
    projects = c.fetchall()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        projects=projects,
        is_owner=viewer_is_owner,
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/create_project", methods=["GET", "POST"])
def create_project():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        description = request.form.get("description", "").strip()
        code = request.form["code"]
        is_public = 1 if "is_public" in request.form else 0

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO projects (user_id, title, description, code, is_public)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], title, description, code, is_public))
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("create_project.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, is_public, description FROM projects WHERE user_id = ?",
        (session["user_id"],),
    )
    projects = c.fetchall()
    conn.close()

    return render_template("dashboard.html", projects=projects)

@app.route("/project/<int:project_id>")
def view_project(project_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT p.id, p.user_id, p.title, p.code, p.is_public, p.description, u.username
        FROM projects p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    """, (project_id,))

    project = c.fetchone()
    conn.close()

    if not project:
        return "Project not found 😢"

    # Allow if public
    if project[4] == 1:
        return render_template("view_project.html", project=project)

    # Allow if owner
    if "user_id" in session and session["user_id"] == project[1]:
        return render_template("view_project.html", project=project)

    return "Project is private 🔒"


@app.route("/edit_project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()

    # Make sure project belongs to logged in user
    c.execute("""
        SELECT id, title, description, code, is_public
        FROM projects 
        WHERE id = ? AND user_id = ?
    """, (project_id, session["user_id"]))

    project = c.fetchone()

    if not project:
        conn.close()
        return "Project not found or not yours 😎"

    if request.method == "POST":
        new_title = request.form["title"]
        new_description = request.form.get("description", "").strip()
        new_code = request.form["code"]
        new_is_public = 1 if "is_public" in request.form else 0

        c.execute("""
            UPDATE projects
            SET title = ?, description = ?, code = ?, is_public = ?
            WHERE id = ?
        """, (new_title, new_description, new_code, new_is_public, project_id))

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    conn.close()
    return render_template("edit_project.html", project=project)

@app.route("/api/data")
def get_data():
    conn = sqlite3.connect("app.db", timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM something")
    data = cursor.fetchall()
    conn.close()
    return {"data": data}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="5050", debug=True)

