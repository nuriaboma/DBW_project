from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager  # <--- Make sure this is imported

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-12345' # Change for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rxinsight.db'

# 1. Initialize Database
db = SQLAlchemy(app)

# 2. Initialize Login Manager (THIS WAS LIKELY MISSING OR WRONG)
login = LoginManager(app)
login.login_view = 'login' # Function name of the login route

# 3. Import Routes and Models AT THE END
# This prevents circular import errors because 'db' and 'login' exist now.
from app import routes, models