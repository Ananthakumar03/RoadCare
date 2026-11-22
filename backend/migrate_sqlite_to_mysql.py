
from pathlib import Path
import sqlite3

from mysql.connector import IntegrityError
from app_mysql import init_db, get_db


BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "roadcare.db"


def migrate():

    if not SQLITE_DB.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {SQLITE_DB}"
        )

    # Create MySQL tables without adding a default admin.
    init_db(seed_admin=False)

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        users = sqlite_conn.execute(
            """
            SELECT id, name, email, password_hash, role, created_at
            FROM users
            ORDER BY id
            """
        ).fetchall()

        complaints = sqlite_conn.execute(
            """
            SELECT id, user_id, title, description, area, road_name,
                   damage_type, severity, traffic_level, accident_count,
                   latitude, longitude, photo, status, admin_note, created_at
            FROM complaints
            ORDER BY id
            """
        ).fetchall()

        # Check that every complaint has a matching user.
        source_user_ids = {
            int(user["id"]) for user in users
        }

        for complaint in complaints:
            if int(complaint["user_id"]) not in source_user_ids:
                raise ValueError(
                    f"Complaint {complaint['id']} has no matching user."
                )

        with get_db() as mysql_conn:

            cursor = mysql_conn.connection.cursor()

            try:
                # Check user ID and email conflicts.
                for user in users:

                    user_id = int(user["id"])
                    email = user["email"]

                    cursor.execute(
                        "SELECT id, email FROM users WHERE id = %s",
                        (user_id,)
                    )
                    existing_by_id = cursor.fetchone()

                    cursor.execute(
                        "SELECT id, email FROM users WHERE email = %s",
                        (email,)
                    )
                    existing_by_email = cursor.fetchone()

                    if (
                        existing_by_id
                        and existing_by_id[1] != email
                    ):
                        raise ValueError(
                            f"MySQL user ID {user_id} belongs to "
                            f"{existing_by_id[1]}, not {email}."
                        )

                    if (
                        existing_by_email
                        and int(existing_by_email[0]) != user_id
                    ):
                        raise ValueError(
                            f"MySQL email {email} belongs to another user."
                        )

                # Check complaint ID conflicts.
                for complaint in complaints:

                    complaint_id = int(complaint["id"])
                    source_user_id = int(complaint["user_id"])

                    cursor.execute(
                        "SELECT user_id FROM complaints WHERE id = %s",
                        (complaint_id,)
                    )
                    existing = cursor.fetchone()

                    if (
                        existing
                        and int(existing[0]) != source_user_id
                    ):
                        raise ValueError(
                            f"Complaint ID {complaint_id} belongs to "
                            "a different user in MySQL."
                        )

                # Migrate users.
                for user in users:

                    cursor.execute(
                        """
                        INSERT INTO users
                        (id, name, email, password_hash, role, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            name = VALUES(name),
                            password_hash = VALUES(password_hash),
                            role = VALUES(role),
                            created_at = VALUES(created_at)
                        """,
                        tuple(user)
                    )

                # Migrate complaints.
                for complaint in complaints:

                    cursor.execute(
                        """
                        INSERT INTO complaints
                        (
                            id, user_id, title, description, area,
                            road_name, damage_type, severity,
                            traffic_level, accident_count,
                            latitude, longitude, photo, status,
                            admin_note, created_at
                        )
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s,
                         %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            user_id = VALUES(user_id),
                            title = VALUES(title),
                            description = VALUES(description),
                            area = VALUES(area),
                            road_name = VALUES(road_name),
                            damage_type = VALUES(damage_type),
                            severity = VALUES(severity),
                            traffic_level = VALUES(traffic_level),
                            accident_count = VALUES(accident_count),
                            latitude = VALUES(latitude),
                            longitude = VALUES(longitude),
                            photo = VALUES(photo),
                            status = VALUES(status),
                            admin_note = VALUES(admin_note),
                            created_at = VALUES(created_at)
                        """,
                        tuple(complaint)
                    )

            finally:
                cursor.close()

        # Add default admin only if it does not already exist.
        init_db(seed_admin=True)

        print("Migration completed successfully.")
        print(f"Users migrated: {len(users)}")
        print(f"Complaints migrated: {len(complaints)}")
        print("Original SQLite database was not changed.")

    finally:
        sqlite_conn.close()


if __name__ == "__main__":

    try:
        migrate()

    except (
        sqlite3.Error,
        IntegrityError,
        ValueError,
        RuntimeError
    ) as error:

        print(f"Migration failed: {error}")
        raise
