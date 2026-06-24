import sys
from app import app, db

try:
    with app.app_context():
        db.create_all()
    print("✓ Database tables created successfully", file=sys.stderr)
except Exception as e:
    print(f"✗ Error creating database: {e}", file=sys.stderr)
    sys.exit(1)
