from datetime import datetime, timezone
from app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    # Using iduser to match your route logic, while keeping it compatible with Flask-Login
    iduser = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    
    @property
    def id(self):
        return self.iduser

    def get_id(self):
        return str(self.iduser)

    def set_password(self, password_input):
        self.password = generate_password_hash(password_input)
        
    def check_password(self, password_input):
        return check_password_hash(self.password, password_input)

class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), index=True, unique=True, nullable=False)
    condition = db.Column(db.String(200)) 
    # Relationship to SideEffect
    side_effects = db.relationship('SideEffect', backref='drug', lazy='dynamic')

class SideEffect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    effect = db.Column(db.String(200), nullable=False)

class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Storing ForeignKeys to the Drug table for better performance
    drug1_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    drug2_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(50))

    # Optional: Relationship to easily access drug names from an interaction object
    drug1 = db.relationship('Drug', foreign_keys=[drug1_id])
    drug2 = db.relationship('Drug', foreign_keys=[drug2_id])

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.iduser'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    medications = db.Column(db.String(500), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    condition = db.Column(db.String(200))