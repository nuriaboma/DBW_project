from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password_repeat = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class SearchForm(FlaskForm):
    # This was already there
    drug_name = StringField('Enter Medication Name(s)', validators=[DataRequired()])
    
    # NEW: Add these fields to match your index.html and routes.py
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[
        ('not_specified', 'Not Specified'), 
        ('male', 'Male'), 
        ('female', 'Female'), 
        ('other', 'Other')
    ])
    condition = StringField('Existing Medical Conditions')
    
    submit = SubmitField('Search')