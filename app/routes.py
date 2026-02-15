from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.forms import LoginForm, RegistrationForm, SearchForm, SimpleSearchForm
from app.models import User, Drug, SideEffect, Interaction, SearchHistory
from app.forms import LoginForm, RegistrationForm, SearchForm, SimpleSearchForm, ConditionSearchForm


# --- 1. PUBLIC ROUTES (Visible to everyone) ---

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')

@app.route('/interactions', methods=['GET', 'POST'])
def public_interactions():
    form = SimpleSearchForm()
    found_drugs = []
    interactions_found = []
    
    if form.validate_on_submit():
        query = form.drug_name.data
        
        # Split medications by comma or space
        drug_names = [name.strip() for name in query.replace(',', ' ').split() if name.strip()]

        # 1. Find Drugs
        for name in drug_names:
            # Search for the drug
            drug = Drug.query.filter(Drug.name.ilike(f'%{name}%')).first()
            if drug:
                found_drugs.append(drug)
            else:
                # Optional: Flash message for drugs not found
                flash(f'Drug "{name}" not found.', 'warning')

        # 2. Find Interactions
        if len(found_drugs) > 1:
            for i in range(len(found_drugs)):
                for j in range(i + 1, len(found_drugs)):
                    conflict = Interaction.query.filter(
                        ((Interaction.drug1_id == found_drugs[i].id) & (Interaction.drug2_id == found_drugs[j].id)) |
                        ((Interaction.drug1_id == found_drugs[j].id) & (Interaction.drug2_id == found_drugs[i].id))
                    ).first()
        
                    if conflict:
                        interactions_found.append(conflict)

    return render_template('public_interactions.html', title='Interaction Checker', form=form, drugs=found_drugs, interactions=interactions_found)

@app.route('/conditions', methods=['GET', 'POST'])
def public_conditions():
    form = ConditionSearchForm()
    matching_drugs = []
    
    if form.validate_on_submit():
        query = form.condition_name.data
        
        # Search for drugs where the 'condition' column contains the user's query
        # We use ilike for case-insensitive search (Diabetes == diabetes)
        matching_drugs = Drug.query.filter(Drug.condition.ilike(f'%{query}%')).all()
        
        if not matching_drugs:
            flash(f'No medications found for condition "{query}".', 'warning')

    return render_template('public_conditions.html', title='Find Medication', form=form, drugs=matching_drugs)


# --- 2. AUTHENTICATION ROUTES (Login/Register) ---

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


# --- 3. PRIVATE ROUTES (Logged-in users only) ---

@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = SearchForm()
    found_drugs = []
    interactions_found = []
    
    # Initialize variables
    query = None
    perform_search = False
    
    # Check if request comes from History (GET) or New Search (POST)
    if request.method == 'GET' and request.args.get('query'):
        # Case 1: Click from History
        query = request.args.get('query')
        # Pre-fill the form
        form.drug_name.data = query
        form.age.data = request.args.get('age')
        form.gender.data = request.args.get('gender')
        form.condition.data = request.args.get('condition')
        perform_search = True
        
    elif form.validate_on_submit():
        # Case 2: New form submission
        query = form.drug_name.data
        perform_search = True
        
        # Only save to history for new searches
        search_entry = SearchHistory(
            user_id=current_user.iduser,
            medications=query,
            age=form.age.data,
            gender=form.gender.data,
            condition=form.condition.data
        )
        db.session.add(search_entry)
        db.session.commit()

    # Common Search Logic
    if perform_search and query:
        drug_names = [name.strip() for name in query.replace(',', ' ').split() if name.strip()]

        # 1. Find Drugs
        for name in drug_names:
            drug = Drug.query.filter(Drug.name.ilike(f'%{name}%')).first()
            if drug:
                found_drugs.append(drug)
            else:
                flash(f'Drug "{name}" not found in database.', 'warning')

        # 2. Find Interactions
        if len(found_drugs) > 1:
            for i in range(len(found_drugs)):
                for j in range(i + 1, len(found_drugs)):
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
    history = SearchHistory.query.filter_by(user_id=current_user.iduser).order_by(SearchHistory.timestamp.desc()).all()
    return render_template('user.html', history=history, user=current_user)