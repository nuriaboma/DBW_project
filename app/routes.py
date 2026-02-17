from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import and_, or_

from app import app, db
from app.forms import LoginForm, RegistrationForm, SearchForm, SimpleSearchForm, ConditionSearchForm
from app.models import User, Drug, Disease, Interaction


# =====================================================
# HOME
# =====================================================
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')


# =====================================================
# 🔍 PUBLIC INTERACTIONS (NO LOGIN)
# =====================================================
@app.route('/interactions', methods=['GET', 'POST'])
def public_interactions():
    form = SimpleSearchForm()
    found_drugs = []
    interactions_found = []

    if form.validate_on_submit():
        query = form.drug_name.data or ""
        drug_names = [d.strip() for d in query.replace(',', ' ').split() if d.strip()]

        # FIND DRUGS
        for name in drug_names:
            drug = Drug.query.filter(
                or_(
                    Drug.Name.ilike(f"%{name}%"),
                    Drug.Brand.ilike(f"%{name}%")
                )
            ).first()

            if drug:
                found_drugs.append(drug)
            else:
                flash(f'Drug "{name}" not found.', 'warning')

        # FIND INTERACTIONS
        if found_drugs:
            for d in found_drugs:
                conflicts = Interaction.query.filter(
                    (Interaction.drug1_id == d.idDrug) | 
                    (Interaction.drug2_id == d.idDrug)
                ).all()

                for conflict in conflicts:
                    if conflict not in interactions_found:
                        interactions_found.append({
                            "drug1_name": conflict.drug1.Name,
                            "drug2_name": conflict.drug2.Name,
                            "severity": conflict.severity
                        })

    return render_template(
        'public_interactions.html',
        title='Interaction Checker',
        form=form,
        drugs=found_drugs,
        interactions=interactions_found
    )


# =====================================================
# 🧬 CONDITION SEARCH
# =====================================================
@app.route('/conditions', methods=['GET', 'POST'])
def public_conditions():
    form = ConditionSearchForm()
    matching_drugs = []

    if form.validate_on_submit():
        query = form.condition_name.data or ""
        print("Condition search:", query)

        disease = Disease.query.filter(
            Disease.Name.ilike(f"%{query}%")
        ).first()

        print("Disease found:", disease)

        if disease:
            matching_drugs = disease.drugs 
            print("Drugs found:", len(matching_drugs))

        else:
            flash(f'Condition "{query}" not found.', 'warning')

    return render_template(
        'public_conditions.html',
        title='Find Medication',
        form=form,
        drugs=matching_drugs
    )


# =====================================================
# LOGIN
# =====================================================
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

        login_user(user)
        return redirect(url_for('index'))

    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# =====================================================
# REGISTER
# =====================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('Registered successfully!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', form=form)


# =====================================================
# 🔐 PRIVATE SEARCH (MAIN PAGE)
# =====================================================
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = SimpleSearchForm()
    found_drugs = []
    interactions_found = []

    if form.validate_on_submit():
        query = form.drug_name.data or ""
        drug_names = [d.strip() for d in query.replace(',', ' ').split() if d.strip()]

        # FIND DRUGS
        for name in drug_names:
            drug = Drug.query.filter(
                or_(
                    Drug.Name.ilike(f"%{name}%"),
                    Drug.Brand.ilike(f"%{name}%")
                )
            ).first()

            if drug:
                found_drugs.append(drug)
            else:
                flash(f'Drug "{name}" not found.', 'warning')

        # FIND INTERACTIONS
        if found_drugs:
            for d in found_drugs:
                conflicts = Interaction.query.filter(
                    (Interaction.drug1_id == d.idDrug) | 
                    (Interaction.drug2_id == d.idDrug)
                ).all()

                for conflict in conflicts:
                    if conflict not in interactions_found:
                        interactions_found.append({
                            "drug1_name": conflict.drug1.Name,
                            "drug2_name": conflict.drug2.Name,
                            "severity": conflict.severity
                        })

    return render_template(
        'public_interactions.html',
        title='Interaction Checker',
        form=form,
        drugs=found_drugs,
        interactions=interactions_found
    )


@app.route('/user')
@login_required
def user():
    # temporary empty page until you implement history
    return render_template('user.html', user=current_user, history=[])
