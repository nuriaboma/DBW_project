from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, PasswordField, BooleanField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, NumberRange
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


class EntryForm(FlaskForm):

    # --- MAIN DRUG INPUT ---
    drug_name = StringField(
        'Enter Medication Name(s)',
        validators=[DataRequired(message="Please enter at least one medication")]
    )

    # --- USER INFO ---
    age = IntegerField(
        'Age',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=120, message="Enter a valid age")
        ]
    )

    gender = SelectField(
        'Gender',
        choices=[
            ('not_specified', 'Not specified'),
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other')
        ],
        default='not_specified'
    )

    condition = StringField(
        'Medical Condition',
        validators=[DataRequired()]
    )

    side_effects = StringField(
        'Side Effects',
        validators=[DataRequired()]
    )

    # --- OPTIONAL FUTURE FIELDS (match Entries table) ---
    dose = FloatField(
        'Dose (optional)',
        validators=[Optional()]
    )

    duration = IntegerField(
        'Duration days (optional)',
        validators=[Optional()]
    )
    treatment_score = FloatField(
        'Treatment Score',
        validators=[
            Optional(),
            NumberRange(min=1, max=10, message="Score must be between 1 and 10")
        ]
    )
    submit = SubmitField('Analyze & Save Profile')


class SimpleSearchForm(FlaskForm):
    # This is the form for the public interaction checker
    drug_name = StringField('Enter Medications', validators=[DataRequired()])
    submit = SubmitField('Check Interactions')


class ConditionSearchForm(FlaskForm):
    condition_name = StringField('Enter Medical Condition (e.g. Diabetes, Pain)', validators=[DataRequired()])
    route_filter = SelectField(
        'Dosage Form',
        choices=[('', 'All')]  
    )
    submit = SubmitField('Find Medications')
