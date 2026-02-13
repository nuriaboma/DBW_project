from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.forms import LoginForm, RegistrationForm, SearchForm
#SideEffect statt DrugReaction!
from app.models import User, Drug, SideEffect, Interaction, SearchHistory


# 1. AUTHENTICATION ROUTES
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

# 2. MAIN SEARCH TOOL
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = SearchForm()
    found_drugs = []
    interactions_found = []

    if form.validate_on_submit():
        # Get data from form
        query = form.drug_name.data
        patient_age = form.age.data
        patient_gender = form.gender.data
        patient_condition = form.condition.data
        
        # Save search to history
        search_entry = SearchHistory(
            user_id=current_user.iduser, # Matches the 'iduser' in your models
            medications=query,
            age=patient_age,
            gender=patient_gender,
            condition=patient_condition
        )
        db.session.add(search_entry)
        db.session.commit()

        # Split medications by comma or space
        drug_names = [name.strip() for name in query.replace(',', ' ').split() if name.strip()]

        # 1. Find Drugs and their Side Effects
        for name in drug_names:
            drug = Drug.query.filter(Drug.name.ilike(f'%{name}%')).first()
            if drug:
                found_drugs.append(drug)
            else:
                flash(f'Drug "{name}" not found in database.', 'warning')

        # 2. Find Interactions between the drugs
        if len(found_drugs) > 1:
            for i in range(len(found_drugs)):
                for j in range(i + 1, len(found_drugs)):
        # Search using the IDs of the drugs we just found
                    conflict = Interaction.query.filter(
                        ((Interaction.drug1_id == found_drugs[i].id) & (Interaction.drug2_id == found_drugs[j].id)) |
                        ((Interaction.drug1_id == found_drugs[j].id) & (Interaction.drug2_id == found_drugs[i].id))
                    ).first()
        
                    if conflict:
                        interactions_found.append(conflict)

    return render_template('index.html', title='Checker', form=form, drugs=found_drugs, interactions=interactions_found)

@app.route('/user')
@login_required
def user():
    # Fetch search history for the profile page
    history = SearchHistory.query.filter_by(user_id=current_user.iduser).order_by(SearchHistory.timestamp.desc()).all()
    return render_template('user.html', history=history, user=current_user)