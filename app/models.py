from datetime import datetime, timezone
from app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login.user_loader
def load_user(id):
    return User.query.get(int(id))


# Association table for Drugs <-> SideEffects
Drugs_has_SideEffects = db.Table(
    "Drugs_has_SideEffects",  # exact MySQL table name
    db.Column("Drugs_idDrug", db.Integer, db.ForeignKey("Drugs.idDrug"), primary_key=True),
    db.Column("SideEffects_idSideEffect", db.Integer, db.ForeignKey("SideEffects.idSideEffect"), primary_key=True)
)

# Association table for Drugs <-> Diseases
Diseases_has_Drugs = db.Table(
    "Diseases_has_Drugs",
    db.Column("Drugs_idDrug", db.Integer, db.ForeignKey("Drugs.idDrug"), primary_key=True),
    db.Column("Diseases_idDisease", db.Integer, db.ForeignKey("Diseases.idDisease"), primary_key=True)
)



class User(UserMixin, db.Model):
    __tablename__ = "Users"   

    iduser = db.Column("idUsers", db.Integer, primary_key=True, autoincrement=True)
    email = db.Column("Email", db.String(100), index=True, unique=True, nullable=False)
    password = db.Column("Password", db.String(255), nullable=False)

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
    __tablename__ = "Drugs"

    idDrug = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(200), index=True, unique=True, nullable=False)
    Brand = db.Column(db.String(200))
    DosageForm = db.Column(db.String(150))
    Route = db.Column(db.String(150))
    PharmClass = db.Column(db.String(250))

    # Relationships
    diseases = db.relationship(
        "Disease",
        secondary=Diseases_has_Drugs,
        back_populates="drugs",
        lazy="select"
    )

    side_effects = db.relationship(
        "SideEffect",
        secondary=Drugs_has_SideEffects,
        backref="drugs",
        lazy="select"
    )

class Disease(db.Model):
    __tablename__ = "Diseases"

    idDisease = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100))

    # Relationship to Drug
    drugs = db.relationship(
        "Drug",
        secondary=Diseases_has_Drugs,
        back_populates="diseases",
        lazy="select"
    )

class SideEffect(db.Model):
    __tablename__ = "SideEffects"

    idSideEffect = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(300))

class Interaction(db.Model):
    __tablename__ = "DrugInteractions"

    # Composite primary key
    drug1_id = db.Column("Drugs_idDrugA", db.Integer, db.ForeignKey("Drugs.idDrug"), primary_key=True)
    drug2_id = db.Column("Drugs_idDrugB", db.Integer, db.ForeignKey("Drugs.idDrug"), primary_key=True)

    severity = db.Column("Level", db.String(8))

    drug1 = db.relationship("Drug", foreign_keys=[drug1_id])
    drug2 = db.relationship("Drug", foreign_keys=[drug2_id])


class Entry(db.Model):
    __tablename__ = 'Entries'
    
    idEntry = db.Column(db.Integer, primary_key=True)
    Age = db.Column(db.Integer)
    Gender = db.Column(db.String(10))
    Dose = db.Column(db.Float)
    DurationDays = db.Column(db.Integer)
    ImprovementScore = db.Column(db.Float)
    
    Drugs_idDrug = db.Column(db.Integer, db.ForeignKey('Drugs.idDrug'))
    Diseases_idDisease = db.Column(db.Integer, db.ForeignKey('Diseases.idDisease'))
    SideEffects_idSideEffect = db.Column(db.Integer, db.ForeignKey('SideEffects.idSideEffect'))
    Users_idUsers = db.Column(db.Integer, db.ForeignKey('Users.idUsers'))
    
    # Relationships
    drug = db.relationship('Drug', backref='entries')
    disease = db.relationship('Disease', backref='entries')
    side_effect = db.relationship('SideEffect', backref='entries')
    user = db.relationship('User', backref='entries')
