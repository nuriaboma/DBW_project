from app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 1. User Loader for Flask-Login
@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 2. User Table
class User(UserMixin, db.Model):
    iduser = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Hashed password

    # Override get_id because Flask-Login looks for 'id', but we use 'iduser'
    def get_id(self):
        return str(self.iduser)

    def set_password(self, password_input):
        self.password = generate_password_hash(password_input)

    def check_password(self, password_input):
        return check_password_hash(self.password, password_input)

    def __repr__(self):
        return f'<User {self.email}>'

# 3. Search History Table
class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.iduser'), nullable=False)
    medications = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<Search {self.medications} by User {self.user_id}>'

# 4. Drug Table
class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # IMPORTANT: This line creates the link to SideEffects!
    # Without this, you get the AttributeError.
    side_effects = db.relationship('SideEffect', backref='drug', lazy=True)

    def __repr__(self):
        return f'<Drug {self.name}>'

# 5. Interaction Table
class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug1_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    drug2_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Interaction {self.severity}>'

# 6. Side Effect Table
class SideEffect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    effect = db.Column(db.String(200), nullable=False) # e.g. "Headache"

    def __repr__(self):
        return f'<SideEffect {self.effect}>'