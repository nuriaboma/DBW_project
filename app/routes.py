from flask import render_template, flash, redirect, url_for, request, make_response, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

from app import app, db
from app.forms import LoginForm, RegistrationForm, EntryForm, SimpleSearchForm, ConditionSearchForm, SideEffectsSearchForm
from app.models import User, Drug, Disease, Interaction, Entry, SideEffect
from datetime import datetime, timedelta
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
            from sqlalchemy import func
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





@app.route('/stats')
@login_required
def stats():

    # ─────────────────────────────
    # GLOBAL STATS (allowed)
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
#  ROUTE 1 — Drug autocomplete API
#  Used by the type-ahead in index.html
#  GET /api/drugs?q=asp  →  ["Aspirin", "Aspartame", ...]
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
#  ROUTE 2 — PDF export
#  POST /export-pdf   (receives same form data as the search)
#  Returns a downloadable PDF report
# ════════════════════════════════════════════════════════════════

@app.route('/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    # ── Re-run the same search logic as your index() route ──────
    drug_input = request.form.get('drug_name', '')
    age        = request.form.get('age', '')
    gender     = request.form.get('gender', '')
    condition  = request.form.get('condition', '')

    drug_names = [d.strip() for d in re.split(r'[,\s]+', drug_input) if d.strip()]

    drugs        = []
    interactions = []

    for name in drug_names:
        drug = Drug.query.filter(Drug.Name.ilike(name)).first()
        if drug:
            drugs.append(drug)

    # Check interactions between found drugs
    for i in range(len(drugs)):
        for j in range(i + 1, len(drugs)):
            inter = Interaction.query.filter(
                ((Interaction.drug1_id == drugs[i].idDrug) & (Interaction.drug2_id == drugs[j].idDrug)) |
                ((Interaction.drug1_id == drugs[j].idDrug) & (Interaction.drug2_id == drugs[i].idDrug))
            ).first()
            if inter:
                inter.drug1_name = drugs[i].Name
                inter.drug2_name = drugs[j].Name
                interactions.append(inter)

    # ── Build PDF in memory ──────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )

    # Colour palette matching RXInsight theme
    NEON    = colors.HexColor('#03e9f4')
    DARK    = colors.HexColor('#0f2027')
    RED     = colors.HexColor('#ff4d4d')
    GREY    = colors.HexColor('#aaaaaa')
    WHITE   = colors.white
    DARKROW = colors.HexColor('#1a2a30')

    styles = getSampleStyleSheet()

    # Custom paragraph styles
    title_style = ParagraphStyle('Title', fontSize=22, textColor=NEON,
                                 alignment=TA_CENTER, fontName='Helvetica-Bold',
                                 spaceAfter=4)
    sub_style   = ParagraphStyle('Sub', fontSize=9, textColor=GREY,
                                 alignment=TA_CENTER, spaceAfter=2)
    h2_style    = ParagraphStyle('H2', fontSize=13, textColor=NEON,
                                 fontName='Helvetica-Bold', spaceBefore=14, spaceAfter=6)
    h3_style    = ParagraphStyle('H3', fontSize=11, textColor=WHITE,
                                 fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=4)
    body_style  = ParagraphStyle('Body', fontSize=9, textColor=WHITE,
                                 leading=14, spaceAfter=3)
    warn_style  = ParagraphStyle('Warn', fontSize=10, textColor=RED,
                                 fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=4)

    story = []

    # ── Header ───────────────────────────────────────────────────
    story.append(Paragraph("RXInsight", title_style))
    story.append(Paragraph("Drug Analysis Report", sub_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  User: {current_user.email}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=NEON, spaceAfter=14))

    # ── Patient info table ───────────────────────────────────────
    story.append(Paragraph("Patient Profile", h2_style))
    patient_data = [
        ['Age', age or '—',  'Gender', gender or '—'],
        ['Condition', condition or 'None', 'Medications', drug_input],
    ]
    pt = Table(patient_data, colWidths=[3*cm, 6*cm, 3*cm, 5.5*cm])
    pt.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), DARKROW),
        ('TEXTCOLOR',   (0,0), (-1,-1), WHITE),
        ('TEXTCOLOR',   (0,0), (0,-1), NEON),
        ('TEXTCOLOR',   (2,0), (2,-1), NEON),
        ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',    (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [DARKROW, colors.HexColor('#243540')]),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#333333')),
        ('PADDING',     (0,0), (-1,-1), 7),
    ]))
    story.append(pt)
    story.append(Spacer(1, 14))

    # ── Interactions ─────────────────────────────────────────────
    if interactions:
        story.append(HRFlowable(width="100%", thickness=1, color=RED, spaceAfter=8))
        story.append(Paragraph("⚠ Critical Interactions", warn_style))
        for inter in interactions:
            inter_data = [
                [f"{inter.drug1_name}  +  {inter.drug2_name}"],
                [inter.description or ''],
                [f"Severity: {inter.severity or 'Unknown'}"],
            ]
            it = Table(inter_data, colWidths=[17.5*cm])
            it.setStyle(TableStyle([
                ('BACKGROUND',  (0,0), (-1,0), colors.HexColor('#3a0000')),
                ('BACKGROUND',  (0,1), (-1,1), colors.HexColor('#2a0000')),
                ('BACKGROUND',  (0,2), (-1,2), colors.HexColor('#1f0000')),
                ('TEXTCOLOR',   (0,0), (-1,0), RED),
                ('TEXTCOLOR',   (0,1), (-1,1), WHITE),
                ('TEXTCOLOR',   (0,2), (-1,2), RED),
                ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',    (0,0), (-1,-1), 9),
                ('PADDING',     (0,0), (-1,-1), 8),
                ('BOX',         (0,0), (-1,-1), 1, RED),
            ]))
            story.append(it)
            story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1, color=RED, spaceAfter=8))

    # ── Drug details ─────────────────────────────────────────────
    if drugs:
        story.append(Paragraph("Drug Analysis", h2_style))
        for drug in drugs:
            story.append(Paragraph(drug.Name, h3_style))
            story.append(Paragraph(
                f"<b><font color='#03e9f4'>Indication:</font></b>  {drug.diseases or 'Not available'}",
                body_style
            ))

            side_effects = [se.effect for se in drug.side_effects[:20]]  # cap at 20
            if side_effects:
                story.append(Paragraph("<b><font color='#aaaaaa'>Known Side Effects:</font></b>", body_style))
                # Two-column layout for side effects
                half = (len(side_effects) + 1) // 2
                col1 = side_effects[:half]
                col2 = side_effects[half:]
                rows = []
                for k in range(half):
                    left  = f"• {col1[k]}" if k < len(col1) else ''
                    right = f"• {col2[k]}" if k < len(col2) else ''
                    rows.append([left, right])
                se_table = Table(rows, colWidths=[8.5*cm, 8.5*cm])
                se_table.setStyle(TableStyle([
                    ('TEXTCOLOR',  (0,0), (-1,-1), GREY),
                    ('FONTSIZE',   (0,0), (-1,-1), 8),
                    ('ROWBACKGROUNDS', (0,0), (-1,-1), [DARKROW, colors.HexColor('#1e2e35')]),
                    ('PADDING',    (0,0), (-1,-1), 5),
                ]))
                story.append(se_table)
            else:
                story.append(Paragraph("No side effects listed.", body_style))

            story.append(Spacer(1, 10))

    # ── Footer ───────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY, spaceBefore=20, spaceAfter=6))
    story.append(Paragraph(
        "This report is generated for informational purposes only and does not constitute medical advice. "
        "Always consult a licensed healthcare professional before making medication decisions.",
        ParagraphStyle('Disclaimer', fontSize=7, textColor=GREY, alignment=TA_CENTER)
    ))

    # ── Build and return ─────────────────────────────────────────
    doc.build(story)
    buffer.seek(0)

    filename = f"RXInsight_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = make_response(buffer.read())
    response.headers['Content-Type']        = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ════════════════════════════════════════════════════════════════
#  ROUTE 3 — Condition autocomplete API
#  Used by the type-ahead in public_conditions.html
#  GET /api/conditions?q=diab  →  ["Diabetes", "Diabetic Neuropathy", ...]
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
