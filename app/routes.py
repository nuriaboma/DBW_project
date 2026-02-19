from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

from app import app, db
from app.forms import LoginForm, RegistrationForm, EntryForm, SimpleSearchForm, ConditionSearchForm
from app.models import User, Drug, Disease, Interaction, Entry, SideEffect
from datetime import datetime, timedelta
from collections import Counter
import re


# =====================================================
# HOME
# =====================================================
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')

@app.route("/tool_selection")
def tool():
    return render_template("tool_selection.html")


# =====================================================
# PUBLIC INTERACTIONS (NO LOGIN)
# =====================================================
@app.route('/interactions', methods=['GET', 'POST'])
def public_interactions():
    form = SimpleSearchForm()
    found_drugs = []
    interactions_by_drug = {}  

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
                drug.Name = drug.Name.title()
                found_drugs.append(drug)


        # FIND INTERACTIONS 
        for drug in found_drugs:
            interactions = []
            conflicts = Interaction.query.filter(
                (Interaction.drug1_id == drug.idDrug) | 
                (Interaction.drug2_id == drug.idDrug)
            ).all()

            for conflict in conflicts:
                interactions.append({
                    "drug1_name": conflict.drug1.Name.title(),
                    "drug2_name": conflict.drug2.Name.title(),
                    "severity": conflict.severity
                })

            interactions_by_drug[drug.Name] = interactions

    return render_template(
        'public_interactions.html',
        title='Interaction Checker',
        form=form,
        drugs=found_drugs,
        interactions_by_drug=interactions_by_drug  
    )


# =====================================================
# CONDITION SEARCH
# =====================================================
ROUTE_NORMALIZATION = {
    "ORAL": "Oral",
    "SUBCUTANEOUS": "Subcutaneous",
    "INTRAMUSCULAR": "Intramuscular",
    "INTRAVENOUS": "Intravenous",
    "TOPICAL": "Topical",
    "INHALATION": "Respiratory (Inhalation)",
    "NASAL": "Nasal",
    "RECTAL": "Rectal",
    "VAGINAL": "Vaginal",
    "OPHTHALMIC": "Ophthalmic",
    "SUBLINGUAL": "Sublingual",
    "BUCCAL": "Buccal",
    "INTRADERMAL": "Intradermal",
    "INTRACAMERAL": "Intracameral",
    "INTRAVITREAL": "Intravitreal",
    "INTRAPERITONEAL": "Intraperitoneal",
    "INTRA-ARTICULAR": "Intra-Articular",
    "INTRAUTERINE": "Intrauterine",
    "INTRACARDIAC": "Intracardiac",
    "AURICULAR (OTIC)": "Auricular (Otic)",
    "UNKNOWN": "Unknown",
    "UNK": "Unknown",
}

def normalize_routes(route_string):
    """
    Returns a list of canonical routes for a given database string.
    Handles multiple routes separated by ; , / and normalizes variations.
    """
    if not route_string:
        return ["Unknown"]

    # Split by ; , or /
    parts = re.split(r"[;/,]", route_string)
    normalized = set()

    for p in parts:
        p_clean = p.strip().upper()
        if p_clean in ROUTE_NORMALIZATION:
            normalized.add(ROUTE_NORMALIZATION[p_clean])
        else:
            normalized.add(p_clean.title())  

    return sorted(normalized)

@app.route('/conditions', methods=['GET', 'POST'])
def public_conditions():
    form = ConditionSearchForm()

    # Populate route dropdown
    all_routes_raw = [r[0] for r in db.session.query(Drug.Route).distinct().all() if r[0]]
    all_routes_set = set()
    for r in all_routes_raw:
        all_routes_set.update(normalize_routes(r))
    dropdown_options = sorted(all_routes_set)
    form.route_filter.choices = [('', 'All')] + [(r, r) for r in dropdown_options]

    drugs_for_condition = []
    matching_drugs = []

    if form.validate_on_submit():
        query = form.condition_name.data or ""
        disease = Disease.query.filter(Disease.Name.ilike(f"%{query}%")).first()

        if disease:
            # prepare all drugs for this condition
            for drug in disease.drugs:
                drug.Name = drug.Name.title()
                if drug.Brand:
                    drug.Brand = drug.Brand.title()
                if drug.Route:
                    drug.Route = drug.Route.title()
                drug.normalized_routes = normalize_routes(drug.Route)
                drug.top_indications = [d.Name for d in drug.diseases[:5]]
                drugs_for_condition.append(drug)

            # filter by selected route
            selected_route = form.route_filter.data
            for drug in drugs_for_condition:
                if selected_route and selected_route != 'All' and selected_route not in drug.normalized_routes:
                    continue
                matching_drugs.append(drug)

        else:
            drugs_for_condition = None 

    return render_template(
        'public_conditions.html',
        title='Find Medication',
        form=form,
        drugs_for_condition=drugs_for_condition,
        drugs=matching_drugs
    )

#========================================
#              SIDE EFFECTS
#========================================

SIDE_EFFECTS_BLACKLIST = [
    "Wrong technique in product usage process",
]

@app.route('/sideeffects', methods=['GET','POST'])
def public_side_effects():
    form = SimpleSearchForm()
    effects = []

    if form.validate_on_submit():
        query = form.drug_name.data or ""
        drug = Drug.query.filter(Drug.Name.ilike(f"%{query}%")).first()

        if drug:
            SIDE_EFFECTS_BLACKLIST = [
                "Wrong technique in product usage process"
            ]
            filtered = [se for se in drug.side_effects if se.Name not in SIDE_EFFECTS_BLACKLIST]
            filtered.sort(key=lambda x: x.Name)
            effects = filtered
        else:
            effects = None

    return render_template(
        'public_side_effects.html',
        form=form,
        effects=effects,
    )


# ==================
#       LOGIN
# ==================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        next_page = request.args.get('next')
        return redirect(next_page or url_for('tool'))


    form = LoginForm()
    login_error = None 

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user is None or not user.check_password(form.password.data):
            login_error = "Invalid email or password"  
        else:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('tool'))

    return render_template(
        'login.html',
        title='Sign In',
        form=form,
        login_error=login_error 
    )


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

        flash('Registered successfully! You can now login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', form=form)


# =====================================================
# PRIVATE SEARCH (ENTRY)
# =====================================================
@app.route('/entry', methods=['GET','POST'])
@login_required
def entry():
    form = EntryForm()

    success_message = None
    error_message = None

    if form.validate_on_submit():

        # ---------- GET FORM DATA ----------
        drug_names_raw = form.drug_name.data
        condition_name = form.condition.data.strip()
        side_effect_name = form.side_effects.data.strip()

        age = form.age.data
        gender = form.gender.data
        dose = form.dose.data
        duration = form.duration.data

        # ---------- PROCESS DRUGS ----------
        drug_names = [d.strip() for d in drug_names_raw.replace(",", " ").split()]
        found_drugs = []

        for name in drug_names:
            drug = Drug.query.filter(
                func.lower(Drug.Name).like(f"%{name.lower()}%")
            ).first()
            if drug:
                found_drugs.append(drug)

        if not found_drugs:
            error_message = f"No medication found with name: {drug_names_raw}"
            return render_template("entry.html", form=form, error_message=error_message)

        # ---------- FIND DISEASE ----------
        disease = Disease.query.filter(
            func.lower(Disease.Name).like(f"%{condition_name.lower()}%")
        ).first()

        if not disease:
            error_message = f"No disease found: {condition_name}"
            return render_template("entry.html", form=form, error_message=error_message)

        # ---------- FIND SIDE EFFECT ----------
        side_effect = SideEffect.query.filter(
            func.lower(SideEffect.Name).like(f"%{side_effect_name.lower()}%")
        ).first()

        if not side_effect:
            error_message = f"No side effect found: {side_effect_name}"
            return render_template("entry.html", form=form, error_message=error_message)

        # ---------- SAVE ENTRIES ----------
        for drug in found_drugs:
            new_entry = Entry(
                Age=age,
                Gender=gender,
                Dose=dose,
                DurationDays=duration,
                Drugs_idDrug=drug.idDrug,
                Diseases_idDisease=disease.idDisease,
                SideEffects_idSideEffect=side_effect.idSideEffect,
                Users_idUsers=current_user.iduser
            )
            db.session.add(new_entry)

        db.session.commit()

        success_message = "Profile saved successfully and interactions analyzed."

        form = EntryForm()

        return render_template(
            "entry.html",
            form=form,
            success_message=success_message
        )

    return render_template("entry.html", form=form)


@app.route('/user')
@login_required
def user():
    # All entries for user (without filters)
    all_entries_query = Entry.query.filter_by(Users_idUsers=current_user.id)\
        .options(
            joinedload(Entry.drug),
            joinedload(Entry.disease),
            joinedload(Entry.side_effect)
        )\
        .order_by(Entry.idEntry.desc())
    all_entries = all_entries_query.all()

    # Base query for filtered results
    query = all_entries_query

    # Filters
    drug_filter = request.args.get('drug', '').strip()
    disease_filter = request.args.get('disease', '').strip()
    side_effect_filter = request.args.get('side_effect', '').strip()

    if drug_filter:
        query = query.join(Entry.drug).filter(Drug.Name.ilike(f"%{drug_filter}%"))
    if disease_filter:
        query = query.join(Entry.disease).filter(Disease.Name.ilike(f"%{disease_filter}%"))
    if side_effect_filter:
        query = query.join(Entry.side_effect).filter(SideEffect.Name.ilike(f"%{side_effect_filter}%"))

    filtered_entries = query.all()

    # Determine messages
    no_entries = len(all_entries) == 0
    no_filter_results = len(all_entries) > 0 and len(filtered_entries) == 0

    return render_template(
        "user.html",
        user=current_user,
        entries=filtered_entries,
        no_entries=no_entries,
        no_filter_results=no_filter_results,
        drug_filter=drug_filter,
        disease_filter=disease_filter,
        side_effect_filter=side_effect_filter
    )


# --- DELETE ENTRY ---
@app.route('/entry/delete/<int:entry_id>', methods=['POST', 'GET'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)

    if entry.Users_idUsers != current_user.id:
        flash("You are not authorized to delete this entry.", "danger")
        return redirect(url_for('user'))

    db.session.delete(entry)
    db.session.commit()
    flash("Entry deleted successfully.", "success")
    return redirect(url_for('user'))


# --- EDIT ENTRY ---
@app.route('/entry/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)

    if entry.Users_idUsers != current_user.id:
        flash("You are not authorized to edit this entry.", "danger")
        return redirect(url_for('user'))

    form = EntryForm(
        drug_name=entry.drug.Name if entry.drug else "",
        age=entry.Age,
        gender=entry.Gender,
        condition=entry.disease.Name if entry.disease else "",
        side_effects=entry.side_effect.Name if entry.side_effect else "",
        dose=entry.Dose,
        duration=entry.DurationDays,
        treatment_score=entry.ImprovementScore
    )

    if form.validate_on_submit():
        entry.Age = form.age.data
        entry.Gender = form.gender.data
        entry.Dose = form.dose.data
        entry.DurationDays = form.duration.data
        entry.ImprovementScore = form.treatment_score.data
        db.session.commit()
        flash("Entry updated successfully.", "success")
        return redirect(url_for('user'))

    return render_template("entry.html", form=form, edit=True, entry=entry)



