from pathlib import Path
import os
from contextlib import AbstractContextManager
from functools import wraps
from datetime import datetime

import mysql.connector
from mysql.connector import IntegrityError
import pandas as pd

from flask import (
    Flask,
    request,
    jsonify,
    session,
    send_from_directory
)
from flask_cors import CORS
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from werkzeug.utils import secure_filename

from analytics import (
    prepare_complaints,
    calculate_priority,
    priority_label
)


# ---------------------------------
# PROJECT PATHS
# ---------------------------------

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# ---------------------------------
# FLASK CONFIGURATION
# ---------------------------------

app = Flask(__name__, static_folder=None)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.secret_key = os.getenv(
    "ROADCARE_SECRET_KEY",
    "change-this-development-secret-before-deployment"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=5 * 1024 * 1024
)

CORS(app, supports_credentials=True)


# ---------------------------------
# MYSQL DATABASE CONFIGURATION
# ---------------------------------

MYSQL_CONFIG = {
    "host": os.getenv("ROADCARE_DB_HOST", "localhost"),
    "port": int(os.getenv("ROADCARE_DB_PORT", "3306")),
    "user": os.getenv("ROADCARE_DB_USER", "root"),
    "password": os.getenv("ROADCARE_DB_PASSWORD", ""),
    "database": os.getenv("ROADCARE_DB_NAME", "roadcare"),
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False
}



class DatabaseSession(AbstractContextManager):
    """MySQL database session adapter."""

    def __init__(self):
        self.connection = mysql.connector.connect(**MYSQL_CONFIG)

    def execute(self, sql, params=()):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()

        return False


def get_db():
    return DatabaseSession()
# ---------------------------------
# DATABASE INITIALIZATION
# ---------------------------------

def init_db(seed_admin=True):

    with get_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(30) NOT NULL DEFAULT 'citizen',
                created_at VARCHAR(30) NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_users_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INT NOT NULL AUTO_INCREMENT,
                user_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                area VARCHAR(255) NOT NULL,
                road_name VARCHAR(255) NOT NULL,
                damage_type VARCHAR(100) NOT NULL,
                severity TINYINT NOT NULL,
                traffic_level TINYINT NOT NULL,
                accident_count INT NOT NULL DEFAULT 0,
                latitude VARCHAR(50) NULL,
                longitude VARCHAR(50) NULL,
                photo VARCHAR(255) NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'Submitted',
                admin_note TEXT,
                created_at VARCHAR(30) NOT NULL,
                PRIMARY KEY (id),
                KEY idx_complaints_user_id (user_id),
                KEY idx_complaints_created_at (created_at),
                CONSTRAINT fk_complaints_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

       
        if seed_admin:

            admin_email = os.getenv(
                "ROADCARE_ADMIN_EMAIL",
                "admin@roadcare.local"
            )

            admin = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (admin_email,)
            ).fetchone()

            if not admin:

                admin_password = os.getenv(
                    "ROADCARE_ADMIN_PASSWORD"
                )

                if admin_password:

                    conn.execute(
                        """
                        INSERT INTO users
                        (name, email, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            "RoadCare Administrator",
                            admin_email,
                            generate_password_hash(admin_password),
                            "admin",
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )

                # ---------------------------------
# CURRENT USER
# ---------------------------------

def current_user():

    if not session.get("user_id"):
        return None

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        return row if row else None
 # ---------------------------------
# LOGIN REQUIRED DECORATOR
# ---------------------------------

def login_required(role=None):

    def decorator(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):

            user = current_user()

            if not user:
                return jsonify({
                    "error": "Please log in first."
                }), 401

            if role and user["role"] != role:
                return jsonify({
                    "error": "You do not have permission for this action."
                }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator
# ---------------------------------
# FILE VALIDATION
# ---------------------------------

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ---------------------------------
# COMPLAINT FORMAT
# ---------------------------------

def complaint_dict(row):

    item = dict(row)

    item["photo_url"] = (
        f"/uploads/{item['photo']}"
        if item.get("photo")
        else None
    )

    return item
# ---------------------------------
# FRONTEND ROUTES
# ---------------------------------

@app.get("/")
def home():

    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


@app.get("/<path:filename>")
def frontend_files(filename):

    candidate = (FRONTEND_DIR / filename).resolve()

    if (
        FRONTEND_DIR.resolve() not in candidate.parents
        or not candidate.is_file()
    ):
        return jsonify({
            "error": "File not found"
        }), 404

    return send_from_directory(
        FRONTEND_DIR,
        filename
    )


@app.get("/uploads/<path:filename>")
def uploaded_files(filename):

    return send_from_directory(
        UPLOAD_DIR,
        filename
    )


# ---------------------------------
# API STATUS
# ---------------------------------

@app.get("/api/status")
def status():

    return jsonify({
        "status": "RoadCare backend running",
        "database": "MySQL",
        "port": 5001
    })


# ---------------------------------
# USER DETAILS
# ---------------------------------

@app.get("/api/me")
def me():

    return jsonify({
        "user": current_user()
    })
# ---------------------------------
# CITIZEN REGISTRATION
# ---------------------------------

@app.post("/api/register")
def register():

    data = (
        request.form
        if request.form
        else (request.get_json(silent=True) or {})
    )

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or len(password) < 6:
        return jsonify({
            "error": "Enter your name, email and a password of at least 6 characters."
        }), 400

    try:
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO users
                (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    "citizen",
                    datetime.now().isoformat(timespec="seconds")
                )
            )

            user_id = cur.lastrowid

        session["user_id"] = user_id

        return jsonify({
            "message": "Registration successful.",
            "user": current_user()
        }), 201

    except IntegrityError:
        return jsonify({
            "error": "This email is already registered."
        }), 409


# ---------------------------------
# USER LOGIN
# ---------------------------------

@app.post("/api/login")
def login():

    data = request.get_json(silent=True) or request.form

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if not user or not check_password_hash(
        user["password_hash"], password
    ):
        return jsonify({
            "error": "Incorrect email or password."
        }), 401

    session["user_id"] = user["id"]

    return jsonify({
        "message": "Login successful.",
        "user": current_user()
    })


# ---------------------------------
# LOGOUT
# ---------------------------------

@app.post("/api/logout")
def logout():

    session.clear()

    return jsonify({
        "message": "Logged out."
    })
# ---------------------------------
# SUBMIT ROAD COMPLAINT
# ---------------------------------

@app.post("/api/complaints")
@login_required("citizen")
def create_complaint():

    data = request.form

    required = [
        "title",
        "description",
        "area",
        "road_name",
        "damage_type",
        "severity",
        "traffic_level"
    ]

    if any(
        not str(data.get(key, "")).strip()
        for key in required
    ):
        return jsonify({
            "error": "Please complete all required complaint fields."
        }), 400

    try:
        severity = int(data["severity"])
        traffic = int(data["traffic_level"])
        accidents = int(data.get("accident_count", 0) or 0)

        if (
            severity not in range(1, 6)
            or traffic not in range(1, 6)
            or accidents < 0
        ):
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Severity and traffic must be 1–5; accident count must be 0 or more."
        }), 400

    photo_name = None
    photo = request.files.get("photo")

    if photo and photo.filename:

        if not allowed_file(photo.filename):
            return jsonify({
                "error": "Photo must be PNG, JPG, JPEG or WEBP."
            }), 400

        safe_name = secure_filename(photo.filename)

        photo_name = (
            f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
        )

        photo.save(UPLOAD_DIR / photo_name)

    with get_db() as conn:

        cur = conn.execute(
            """
            INSERT INTO complaints
            (
                user_id, title, description, area, road_name,
                damage_type, severity, traffic_level,
                accident_count, latitude, longitude,
                photo, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                data["title"].strip(),
                data["description"].strip(),
                data["area"].strip(),
                data["road_name"].strip(),
                data["damage_type"],
                severity,
                traffic,
                accidents,
                data.get("latitude", "").strip(),
                data.get("longitude", "").strip(),
                photo_name,
                "Submitted",
                datetime.now().isoformat(timespec="seconds")
            )
        )

        complaint_id = cur.lastrowid

    return jsonify({
        "message": "Road complaint submitted successfully.",
        "complaint_id": complaint_id
    }), 201
# ---------------------------------
# VIEW COMPLAINTS
# ---------------------------------

@app.get("/api/complaints")
@login_required()
def list_complaints():

    user = current_user()

    with get_db() as conn:

        if user["role"] == "admin":

            rows = conn.execute(
                """
                SELECT c.*, u.name AS citizen_name,
                       u.email AS citizen_email
                FROM complaints c
                JOIN users u ON c.user_id = u.id
                ORDER BY c.created_at DESC
                """
            ).fetchall()

        else:

            rows = conn.execute(
                """
                SELECT *
                FROM complaints
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user["id"],)
            ).fetchall()

    return jsonify({
        "complaints": [
            complaint_dict(row) for row in rows
        ]
    })
# ---------------------------------
# ADMIN UPDATE COMPLAINT
# ---------------------------------

@app.patch("/api/complaints/<int:complaint_id>")
@login_required("admin")
def update_complaint(complaint_id):

    data = request.get_json(silent=True) or {}

    status_value = data.get("status")
    note = str(data.get("admin_note", "")).strip()

    allowed_statuses = {
        "Submitted",
        "Verified",
        "Repair in Progress",
        "Resolved",
        "Rejected"
    }

    if status_value not in allowed_statuses:
        return jsonify({
            "error": "Invalid complaint status."
        }), 400

    with get_db() as conn:

        cur = conn.execute(
            """
            UPDATE complaints
            SET status = ?, admin_note = ?
            WHERE id = ?
            """,
            (status_value, note, complaint_id)
        )

        if cur.rowcount == 0:
            return jsonify({
                "error": "Complaint not found."
            }), 404

    return jsonify({
        "message": "Complaint updated successfully."
    })
# ---------------------------------
# DATA ANALYTICS
# ---------------------------------

@app.get("/api/analytics")
@login_required("admin")
def analytics():

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT id, title, area, damage_type,
                   severity, traffic_level, accident_count,
                   status, created_at
            FROM complaints
            ORDER BY created_at DESC
            """
        ).fetchall()

        all_rows = conn.execute(
            "SELECT * FROM complaints"
        ).fetchall()

    df = prepare_complaints(
        [list(row.values()) for row in rows]
    )

    if df.empty:
        return jsonify({
            "total": 0,
            "pending": 0,
            "resolved": 0,
            "by_area": [],
            "by_severity": [],
            "by_month": [],
            "priorities": []
        })

    by_area = (
        df.groupby("area")
        .size()
        .sort_values(ascending=False)
        .head(8)
    )

    by_severity = (
        df.groupby("severity")
        .size()
        .sort_index()
    )

    df["month"] = (
        pd.to_datetime(
            df["created_at"],
            errors="coerce"
        ).dt.strftime("%b %Y")
    )

    by_month = df.groupby("month").size()

    priorities = []

    area_counts = df.groupby("area").size().to_dict()

    for row in all_rows:

        item = dict(row)

        score = calculate_priority(
            item,
            area_counts.get(item["area"], 1)
        )

        priorities.append({
            "id": item["id"],
            "title": item["title"],
            "area": item["area"],
            "score": score,
            "level": priority_label(score),
            "status": item["status"]
        })

    priorities.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return jsonify({

        "total": int(len(df)),

        "pending": int(
            df["status"].isin([
                "Submitted",
                "Verified",
                "Repair in Progress"
            ]).sum()
        ),

        "resolved": int(
            (df["status"] == "Resolved").sum()
        ),

        "by_area": [
            {
                "label": str(key),
                "value": int(value)
            }
            for key, value in by_area.items()
        ],

        "by_severity": [
            {
                "label": f"Level {int(key)}",
                "value": int(value)
            }
            for key, value in by_severity.items()
        ],

        "by_month": [
            {
                "label": str(key),
                "value": int(value)
            }
            for key, value in by_month.items()
        ],

        "priorities": priorities
    })


# ---------------------------------
# ROAD IMPACT HEATMAP API
# ---------------------------------

@app.get("/api/road-impact-heatmap")
@login_required("admin")
def road_impact_heatmap():

    with get_db() as conn:

        rows = conn.execute("""
            SELECT
                id,
                area,
                road_name,
                damage_type,
                severity,
                traffic_level,
                accident_count,
                status,
                latitude,
                longitude
            FROM complaints
            WHERE latitude IS NOT NULL
              AND latitude <> ''
              AND longitude IS NOT NULL
              AND longitude <> ''
        """).fetchall()

    locations = {}

    for row in rows:

        try:
            lat = float(row["latitude"])
            lng = float(row["longitude"])

            # Basic coordinate validation
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                continue

        except (ValueError, TypeError):
            continue

        key = (lat, lng)

        if key not in locations:
            locations[key] = {
                "latitude": lat,
                "longitude": lng,
                "area": row["area"],
                "complaint_count": 0,
                "total_severity": 0,
                "total_accidents": 0,
                "total_traffic": 0,
                "complaints": []
            }

        item = locations[key]

        item["complaint_count"] += 1
        item["total_severity"] += int(row["severity"] or 0)
        item["total_accidents"] += int(row["accident_count"] or 0)
        item["total_traffic"] += int(row["traffic_level"] or 0)

        item["complaints"].append({
            "id": row["id"],
            "road_name": row["road_name"],
            "damage_type": row["damage_type"],
            "severity": row["severity"],
            "status": row["status"]
        })

    heatmap_points = []

    for item in locations.values():

        count = item["complaint_count"]

        average_severity = (
            item["total_severity"] / count
        )

        average_traffic = (
            item["total_traffic"] / count
        )

        # Demo impact index: 0–100
        impact_score = min(100, round(
            (average_severity / 5 * 40)
            + (average_traffic / 5 * 25)
            + (min(item["total_accidents"], 10) / 10 * 20)
            + (min(count, 10) / 10 * 15)
        ))

        if impact_score >= 70:
            level = "High"
        elif impact_score >= 40:
            level = "Medium"
        else:
            level = "Low"

        heatmap_points.append({
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "area": item["area"],
            "complaint_count": count,
            "average_severity": round(average_severity, 2),
            "total_accidents": item["total_accidents"],
            "impact_score": impact_score,
            "impact_level": level,
            "complaints": item["complaints"]
        })

    heatmap_points.sort(
        key=lambda x: x["impact_score"],
        reverse=True
    )

    return jsonify({
        "total_locations": len(heatmap_points),
        "total_mapped_complaints": sum(
            item["complaint_count"]
            for item in heatmap_points
        ),
        "location_type": "Area-level approximate demo coordinates",
        "heatmap": heatmap_points
    })
# ---------------------------------
# RUN ROADCARE WITH MYSQL
# ---------------------------------

print("Starting RoadCare MySQL...")

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )


