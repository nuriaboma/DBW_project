from flask import render_template, flash, redirect, url_for, request, make_response, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

from app import app, db
from app.forms import LoginForm, RegistrationForm, EntryForm, SimpleSearchForm, ConditionSearchForm, SideEffectsSearchForm
from app.models import User, Drug, Disease, Interaction, Entry, SideEffect
from datetime import datetime, timedelta
import re
from collections import Counter

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem
from reportlab.lib.enums import TA_CENTER
from io import BytesIO


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
    query = ""

    if form.validate_on_submit():
        # Case A: User typed something into the form and clicked submit
        query = form.drug_name.data or ""
        
    elif request.method == 'GET' and request.args.get('prefill_drug'):
        # Case B: User arrived via the link from the Condition Tool
        query = request.args.get('prefill_drug')
        form.drug_name.data = query  # Automatically populate the search field

    # 3. If we have a query (regardless of the source), start the search!
    if query:
        drug_names = [d.strip() for d in form.drug_name.data.split(",") if d.strip()]

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
    form = SideEffectsSearchForm() # Your preferred form name
    effects = []
    top_effects = []   # Add this to prevent crashes
    total_reports = 0  # Add this to prevent crashes

    if form.validate_on_submit():
        query = form.drug_name.data or ""
        drug = Drug.query.filter(Drug.Name.ilike(f"%{query}%")).first()

        if drug:
            SIDE_EFFECTS_BLACKLIST = ["Wrong technique in product usage process"]

            # Count how many entries in the Entry table reported each side effect for this drug
            freq_rows = (
                db.session.query(SideEffect, func.count(Entry.idEntry).label('cnt'))
                .join(Entry, Entry.SideEffects_idSideEffect == SideEffect.idSideEffect)
                .filter(Entry.Drugs_idDrug == drug.idDrug)
                .filter(SideEffect.Name.notin_(SIDE_EFFECTS_BLACKLIST))
                .group_by(SideEffect.idSideEffect)
                .order_by(func.count(Entry.idEntry).desc())
                .all()
            )

            # Build frequency map
            freq_map = {se.idSideEffect: cnt for se, cnt in freq_rows}
            total_reports = sum(freq_map.values())

            # All side effects for this drug (alphabetical), excluding blacklist
            all_effects = sorted(
                [se for se in drug.side_effects if se.Name not in SIDE_EFFECTS_BLACKLIST],
                key=lambda x: x.Name
            )

            # Top 5 — prefer those with known frequency, fill from alphabetical if needed
            seen_ids = set()
            top_effects = []
            # First add frequency-ranked ones
            for se, cnt in freq_rows[:5]:
                top_effects.append({'name': se.Name, 'count': cnt})
                seen_ids.add(se.idSideEffect)
            # Fill up to 5 if fewer than 5 had entries
            for se in all_effects:
                if len(top_effects) >= 5:
                    break
                if se.idSideEffect not in seen_ids:
                    top_effects.append({'name': se.Name, 'count': 0})
                    seen_ids.add(se.idSideEffect)

            effects = all_effects
        else:
            effects = None

    return render_template(
        'public_side_effects.html',
        form=form,
        effects=effects,
        top_effects=top_effects,
        total_reports=total_reports,
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
        if form.gender.data.lower() == 'not_specified':
            error_message = f"Please select a gender"
            return render_template("entry.html", form=form, error_message=error_message)
        else:
            gender = form.gender.data
        dose = form.dose.data
        duration = form.duration.data
        treatmentScore=form.treatment_score.data

        # ---------- PROCESS DRUGS ----------
        drug_names = [d.strip() for d in form.drug_name.data.split(",") if d.strip()]
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
        saved_entries = []
        for drug in found_drugs:
            new_entry = Entry(
                Age=age,
                Gender=gender,
                Dose=dose,
                DurationDays=duration,
                Drugs_idDrug=drug.idDrug,
                Diseases_idDisease=disease.idDisease,
                SideEffects_idSideEffect=side_effect.idSideEffect,
                Users_idUsers=current_user.iduser,
                ImprovementScore=treatmentScore
            )
            db.session.add(new_entry)
            saved_entries.append(new_entry)

        db.session.commit()

        success_message = "Profile saved successfully and analyzed."

        last_entry = saved_entries[-1] if saved_entries else None
        disease_name = last_entry.disease.Name if last_entry and last_entry.disease else None
        form = EntryForm()

        return render_template(
            "entry.html",
            form=form,
            success_message=success_message,
            show_analysis_buttons=True,
            last_profile=last_entry,
            disease_name=disease_name
        )

    return render_template("entry.html", form=form)

@app.route('/similar-analysis')
@login_required
def similar_analysis():

    entry_id = request.args.get("entry_id")

    if not entry_id:
        flash("Entry not found for analysis.", "error")
        return redirect(url_for("entry"))

    entry = Entry.query.get(entry_id)

    if not entry:
        flash("Entry does not exist.", "error")
        return redirect(url_for("entry"))

    age = entry.Age
    gender = entry.Gender
    disease_id = entry.Diseases_idDisease


    min_age = age - 10
    max_age = age + 10

    similar_entries = Entry.query.filter(
        Entry.Gender == gender,
        Entry.Diseases_idDisease == disease_id,
        Entry.Age.between(min_age, max_age),
        Entry.Users_idUsers != current_user.iduser 
    ).all()

    total_similar = len(similar_entries)
    disease_id = request.args.get("disease_id")

    disease_name = None
    if disease_id:
        disease = Disease.query.get(disease_id)
        if disease:
            disease_name = disease.Name

    # --- Count drugs ---
    drug_counter = Counter()
    side_counter = Counter()
    scores = []

    for e in similar_entries:
        drug_counter[e.drug.Name] += 1
        side_counter[e.side_effect.Name] += 1
        if e.ImprovementScore:
            scores.append(e.ImprovementScore)

    top_drugs = drug_counter.most_common(5)
    top_side_effects = side_counter.most_common(5)
    avg_score = round(sum(scores)/len(scores), 1) if scores else None

    return render_template(
        'similar_analysis.html',
        total_similar=total_similar,
        top_drugs=top_drugs,
        top_side_effects=top_side_effects,
        avg_score=avg_score,
        age=age,
        gender=gender,
        disease_name=disease_name 
    )


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
        flash("You are not authorized to delete this entry.", "error")
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
        flash("You are not authorized to modify this entry.", "error")
        return redirect(url_for('user'))

    form = EntryForm(
        drug_name=entry.drug.Name,
        age=entry.Age,
        gender=entry.Gender,
        condition=entry.disease.Name,
        side_effects=entry.side_effect.Name,
        dose=entry.Dose,
        duration=entry.DurationDays,
        treatment_score=entry.ImprovementScore
    )

    if form.validate_on_submit():
        drug_names = [d.strip() for d in form.drug_name.data.split(",") if d.strip()]
        found_drugs = []

        for name in drug_names:
            drug = Drug.query.filter(
                func.lower(Drug.Name).like(f"%{name.lower()}%")
            ).first()
            if drug:
                found_drugs.append(drug)


        disease = Disease.query.filter(
            func.lower(Disease.Name).like(f"%{form.condition.data.lower()}%")
        ).first()

        side_effect = SideEffect.query.filter(
            func.lower(SideEffect.Name).like(f"%{form.side_effects.data.lower()}%")
        ).first()

        for drug in found_drugs:
            entry.Age = form.age.data
            entry.Gender = form.gender.data
            entry.Dose = form.dose.data
            entry.DurationDays = form.duration.data
            entry.ImprovementScore = form.treatment_score.data
            entry.Drugs_idDrug=drug.idDrug,
            entry.Diseases_idDisease=disease.idDisease,
            entry.SideEffects_idSideEffect=side_effect.idSideEffect,
            
        db.session.commit()
        flash("Entry modified successfully.", "success")
        return redirect(url_for('user'))

    return render_template("entry.html", form=form, edit=True, entry=entry)


@app.route('/stats')
@login_required
def stats():

    # ─────────────────────────────
    # GLOBAL STATS
    # ─────────────────────────────
    total_drugs = Drug.query.count()
    total_interactions_db = Interaction.query.count()
    total_sideeffects_db = SideEffect.query.count()

    # ─────────────────────────────
    # USER STATS
    # ─────────────────────────────
    user_entries_query = Entry.query.filter_by(
        Users_idUsers=current_user.iduser
    )

    total_user_entries = user_entries_query.count()

    # Entries last 7 days
    today = datetime.utcnow().date()
    labels = []
    data = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        count = user_entries_query.filter(
            func.date(Entry.Date) == day   
        ).count()

        labels.append(day.strftime('%b %d'))
        data.append(count)

    # ─────────────────────────────
    # USER MOST USED DRUGS
    # ─────────────────────────────
    drug_usage = (
        db.session.query(Drug.Name, func.count(Entry.idEntry))
        .join(Entry, Entry.Drugs_idDrug == Drug.idDrug)
        .filter(Entry.Users_idUsers == current_user.iduser)
        .group_by(Drug.idDrug)
        .order_by(desc(func.count(Entry.idEntry)))
        .limit(5)
        .all()
    )

    drug_labels = [d[0] for d in drug_usage]
    drug_data = [d[1] for d in drug_usage]

    most_used_drug = drug_labels[0] if drug_labels else None

    # ─────────────────────────────
    # RENDER
    # ─────────────────────────────
    return render_template(
        'stats.html',
        title="My Statistics",

        # Global
        total_drugs=total_drugs,
        total_interactions_db=total_interactions_db,
        total_sideeffects_db=total_sideeffects_db,

        # User
        total_user_entries=total_user_entries,
        search_labels=labels,
        search_data=data,
        drug_labels=drug_labels,
        drug_data=drug_data,
        most_used_drug=most_used_drug,
    )



# ════════════════════════════════════════════════════════════════
#  Drug autocomplete API
# ════════════════════════════════════════════════════════════════

@app.route('/api/drugs')
def api_drugs():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    results = (
        Drug.query
        .filter(Drug.Name.ilike(f'{q}%'))
        .order_by(Drug.Name)
        .limit(8)
        .all()
    )
    return jsonify([d.Name for d in results])


# ════════════════════════════════════════════════════════════════
#  PDF export
# ════════════════════════════════════════════════════════════════

@app.route('/export_pdf/<int:entry_id>')
@login_required
def export_pdf(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    severity_order = {
        "Major": 3,
        "Moderate": 2,
        "Minor": 1,
        "Unknown": 0
    }

    severity_colors = {
        "Major": colors.Color(255/255, 77/255, 77/255, alpha=51/255),
        "Moderate": colors.Color(245/255, 144/255, 11/255, alpha=51/255),
        "Minor": colors.Color(255/255, 255/255, 0/255, alpha=51/255),
        "Unknown": colors.Color(150/255, 150/255, 150/255, alpha=38/255)
    }

    # ── Get latest user profile ─────────────────────────────
    latest = Entry.query.filter_by(
        Users_idUsers=current_user.iduser
    ).order_by(Entry.idEntry.desc()).first()

    if not latest:
        return "No data available."

    age = latest.Age
    gender = latest.Gender
    disease = Disease.query.get(latest.Diseases_idDisease)
    disease_name = disease.Name if disease else "Unknown"

    # Get related entries (same profile)
    entries = Entry.query.filter_by(
        Users_idUsers=current_user.iduser,
        Age=age,
        Gender=gender,
        Diseases_idDisease=latest.Diseases_idDisease
    ).all()

    # Unique drugs only
    drug_ids = {e.Drugs_idDrug for e in entries}
    drugs = Drug.query.filter(Drug.idDrug.in_(drug_ids)).all()

    # ── Interactions ─────────────────────────────────────────
    interactions_by_drug = {}

    for drug in drugs:
        conflicts = Interaction.query.filter(
            (Interaction.drug1_id == drug.idDrug) |
            (Interaction.drug2_id == drug.idDrug)
        ).all()

        unique = set()
        drug_interactions = []

        for conflict in conflicts:
            d1 = conflict.drug1.Name.title()
            d2 = conflict.drug2.Name.title()
            sev = conflict.severity or "Unknown"

            key = tuple(sorted([d1, d2]))
            if key in unique:
                continue
            unique.add(key)

            drug_interactions.append({
                "drug1_name": d1,
                "drug2_name": d2,
                "severity": sev
            })

        # Sort by severity (highest first)
        drug_interactions.sort(
            key=lambda x: severity_order.get(x["severity"], 0),
            reverse=True
        )

        interactions_by_drug[drug.Name.title()] = drug_interactions
    # ── PDF setup ────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    # Colors (cleaner clinical look)
    NEON = colors.HexColor("#19d8e2")
    DARK = colors.HexColor("#1a2a30")
    GREY = colors.HexColor("#666666")
    LIGHT = colors.HexColor("#f4f7f9")
    RED = colors.HexColor("#d9534f")

    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        'Title', fontSize=20, textColor=NEON,
        alignment=TA_CENTER, spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    subtitle = ParagraphStyle(
        'Sub', fontSize=9, textColor=GREY,
        alignment=TA_CENTER, spaceAfter=12
    )

    h2 = ParagraphStyle(
        'H2', fontSize=13, textColor=NEON,
        fontName='Helvetica-Bold', spaceBefore=12, spaceAfter=6
    )

    h3 = ParagraphStyle(
        'H3', fontSize=12, textColor=DARK,
        fontName='Helvetica-Bold', spaceBefore=12, spaceAfter=6
    )

    normal = ParagraphStyle(
        'Normal', fontSize=10, textColor=colors.black, leading=14
    )

    small = ParagraphStyle(
        'Small', fontSize=8, textColor=GREY
    )

    story = []

    # ── Header ───────────────────────────────────────────────
    story.append(Paragraph("RXInsight - Patient Report", title))
    story.append(Paragraph(
        f"<br/>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {current_user.email}",
        subtitle
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=NEON))

    # ── Patient profile ───────────────────────────────────────
    story.append(Paragraph("Patient Profile", h2))

    profile_items = [
        f"<b>Age:</b> {age}",
        f"<b>Gender:</b> {gender}",
        f"<b>Condition:</b> {disease_name}",
        f"<b>Medications:</b> {', '.join(d.Name.title() for d in drugs)}"
    ]

    profile_list = ListFlowable(
        [ListItem(Paragraph(item, normal)) for item in profile_items],
        bulletType='bullet',
        leftIndent=10,
        spaceBefore=4,
        spaceAfter=8
    )

    story.append(profile_list)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=6))

    # ── Interactions section (ALWAYS shown) ───────────────────
    story.append(Paragraph("Drug Interactions", h2))

    has_any_interactions = any(interactions_by_drug.values())

    if has_any_interactions:

        for drug_name, interactions in interactions_by_drug.items():
            story.append(Paragraph(drug_name, h3))

            if interactions:
                rows = []
                row_colors = []

                for inter in interactions:
                    text = f"{inter['drug1_name']}  +  {inter['drug2_name']}"
                    sev  = inter["severity"]

                    rows.append([text, sev])
                    row_colors.append(severity_colors.get(sev, severity_colors["Unknown"]))

                table = Table(rows, colWidths=[12*cm, 5*cm])

                style = [
                    ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor("#000000")),
                    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                    ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#333333')),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]

                # Apply background per row
                for i, color in enumerate(row_colors):
                    style.append(('BACKGROUND', (0,i), (-1,i), color))

                table.setStyle(TableStyle(style))
                story.append(table)

            else:
                story.append(Paragraph("No known interactions.", normal))

            story.append(Spacer(1, 8))

    else:
        story.append(Paragraph("No known interactions for the selected medications.", normal))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=6))


    # ── Side effects ──────────────────────────────────────────
    story.append(Paragraph("Possible Side Effects", h2))

    for drug in drugs:
        story.append(Paragraph(f"<b>{drug.Name.title()}</b>", normal))

        effects = list({se.Name for se in drug.side_effects[:15]})

        if effects:
            # two-column layout
            half = (len(effects) + 1) // 2
            rows = []
            for i in range(half):
                left = effects[i] if i < len(effects) else ""
                right = effects[i+half] if i+half < len(effects) else ""
                rows.append([left, right])

            se_table = Table(rows, colWidths=[8*cm, 8*cm])
            se_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), LIGHT),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('PADDING', (0,0), (-1,-1), 4)
            ]))
            story.append(se_table)
        else:
            story.append(Paragraph("No data available.", small))

        story.append(Spacer(1, 6))

    # ── Footer ────────────────────────────────────────────────
    def draw_footer(canvas, doc):
        canvas.saveState()

        footer_y = 1.5 * cm

        # Line
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, footer_y + 10, A4[0] - 2*cm, footer_y + 10)

        # Text
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)

        canvas.drawCentredString(
            A4[0] / 2,
            footer_y,
            "RXInsight Report — For informational purposes only. Not medical advice."
        )

        # Page number (optional but professional)
        canvas.drawRightString(
            A4[0] - 2*cm,
            footer_y - 10,
            f"Page {doc.page}"
        )

        canvas.restoreState()

    # Build
    doc.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer
    )
    buffer.seek(0)

    filename = f"RXInsight_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


# ════════════════════════════════════════════════════════════════
# Condition autocomplete API
# ════════════════════════════════════════════════════════════════

@app.route('/api/conditions')
def api_conditions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    results = (
        Disease.query
        .filter(Disease.Name.ilike(f'%{q}%'))
        .order_by(Disease.Name)
        .limit(8)
        .all()
    )

    return jsonify([d.Name for d in results if d.Name])

# ════════════════════════════════════════════════════════════════
# Side effects autocomplete API
# ════════════════════════════════════════════════════════════════

@app.route('/api/sideeffects')
def api_sideeffects():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    results = (
        SideEffect.query
        .filter(SideEffect.Name.ilike(f'%{q}%'))
        .order_by(SideEffect.Name)
        .limit(8)
        .all()
    )

    return jsonify([s.Name for s in results if s.Name])