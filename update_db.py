from app import app, db
from app.models import User

with app.app_context():
    # This creates the 'user' table if it doesn't exist
    db.create_all()
    print("Database updated! User table created successfully.")
