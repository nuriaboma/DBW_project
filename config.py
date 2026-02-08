import os

class Config:
    # Security key for session management (keep this secret in production)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-this-key'
    
    # Database path (creates a file named 'rxinsight.db' in your folder)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///rxinsight.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
