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
    # This is the main form for logged-in users
    drug_name = StringField('Enter Medication Name(s)', validators=[DataRequired()])
    
    # Extra fields for the detailed analysis
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[
        ('not_specified', 'Not Specified'), 
        ('male', 'Male'), 
        ('female', 'Female'), 
        ('other', 'Other')
    ])
    condition = StringField('Existing Medical Conditions')
    
    submit = SubmitField('Search')

class SimpleSearchForm(FlaskForm):
    # This is the form for the public interaction checker
    drug_name = StringField('Enter Medications', validators=[DataRequired()])
    submit = SubmitField('Check Interactions')


class ConditionSearchForm(FlaskForm):
    condition_name = StringField('Enter Medical Condition (e.g. Diabetes, Pain)', validators=[DataRequired()])
    submit = SubmitField('Find Medications')