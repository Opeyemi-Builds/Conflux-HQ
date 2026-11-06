"""Create all tables: python -m scripts.init_db (run from backend/)."""
from app.db.init_db import init_db

if __name__ == "__main__":
    init_db()
    print("Tables created.")
