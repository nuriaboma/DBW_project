import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# 1. Initialize the Flask App
app = Flask(__name__)
app.config.from_object(Config)

# 2. Initialize Database and Login Manager
db = SQLAlchemy(app)
login = LoginManager(app)

# 3. Tell Flask-Login which route handles logging in
# (This ensures @login_required redirects people to the login page)
login.login_view = 'login' 
login.login_message_category = 'info'

# 4. Import routes and models at the bottom to avoid circular imports
from app import routes, models