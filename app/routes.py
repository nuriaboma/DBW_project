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


# ─────────────────────────────────────────────────────────────
#  ADD THIS TO YOUR app/routes.py (or wherever your routes live)
# ─────────────────────────────────────────────────────────────
#
#  Required imports (add to your existing imports):
#
#    from sqlalchemy import func, desc
#    from datetime import datetime, timedelta
#    from collections import Counter
#    import re
#
#  This route assumes your models are:
#    - Drug           (id, name, condition)
#    - Interaction    (id, drug1_id, drug2_id, ...)
#    - SideEffect     (id, drug_id, effect)
#    - SearchHistory  (id, user_id, medications, timestamp, ...)
#    - User           (iduser, email, ...)
#
#  Adjust model/field names below to match your actual models.
# ─────────────────────────────────────────────────────────────

from sqlalchemy import func, desc
from datetime import datetime, timedelta
from collections import Counter
import re


@app.route('/stats')
@login_required          # remove this decorator if you want it public
def stats():

    # ── 1. DATABASE STATS ──────────────────────────────────────
    total_drugs            = Drug.query.count()
    total_interactions_db  = Interaction.query.count()
    total_users            = User.query.count()

    # Average side effects per drug
    total_side_effects = SideEffect.query.count()
    avg_side_effects = round(total_side_effects / total_drugs, 1) if total_drugs else 0

    # Drug with the most side effects
    most_effects_row = (
        db.session.query(Drug.name, func.count(SideEffect.id).label('cnt'))
        .join(SideEffect, SideEffect.drug_id == Drug.id)
        .group_by(Drug.id)
        .order_by(desc('cnt'))
        .first()
    )
    most_effects_drug = most_effects_row.name if most_effects_row else None


    # ── 2. USAGE STATS (from SearchHistory) ────────────────────
    total_searches = SearchHistory.query.count()

    # Count how many searches actually returned an interaction
    # We look at searches where the result had an interaction flag.
    # If you store a boolean/count on SearchHistory, use that directly.
    # Otherwise, approximate by counting rows where medications contains
    # at least 2 drugs (rough proxy):
    total_interactions_found = (
        SearchHistory.query
        .filter(SearchHistory.medications.like('%,%'))   # has a comma → 2+ drugs
        .count()
    )


    # ── 3. SEARCHES OVER THE LAST 7 DAYS ───────────────────────
    today = datetime.utcnow().date()
    search_labels = []
    search_data   = []

    for i in range(6, -1, -1):          # 6 days ago … today
        day = today - timedelta(days=i)
        count = (
            SearchHistory.query
            .filter(func.date(SearchHistory.timestamp) == day)
            .count()
        )
        search_labels.append(day.strftime('%b %d'))
        search_data.append(count)


    # ── 4. TOP 5 SEARCHED DRUGS ────────────────────────────────
    # Parse the free-text 'medications' field and count occurrences
    all_meds_raw = db.session.query(SearchHistory.medications).all()

    drug_counter = Counter()
    for (med_string,) in all_meds_raw:
        if med_string:
            # Split on comma or space, clean up, title-case
            names = [n.strip().title() for n in re.split(r'[,\s]+', med_string) if n.strip()]
            drug_counter.update(names)

    top_drugs   = drug_counter.most_common(5)
    drug_labels = [d[0] for d in top_drugs]
    drug_data   = [d[1] for d in top_drugs]

    most_searched_drug = drug_labels[0] if drug_labels else None


    # ── 5. MOST ACTIVE USERS ───────────────────────────────────
    top_users = (
        db.session.query(
            User.email,
            func.count(SearchHistory.id).label('search_count')
        )
        .join(SearchHistory, SearchHistory.user_id == User.iduser)
        .group_by(User.iduser)
        .order_by(desc('search_count'))
        .limit(8)
        .all()
    )


    # ── 6. RENDER ──────────────────────────────────────────────
    return render_template(
        'stats.html',
        title                  = 'Stats',

        # KPI cards
        total_searches         = total_searches,
        total_interactions_found = total_interactions_found,
        total_users            = total_users,
        total_drugs            = total_drugs,
        total_interactions_db  = total_interactions_db,

        # Charts
        search_labels          = search_labels,
        search_data            = search_data,
        drug_labels            = drug_labels,
        drug_data              = drug_data,

        # Table & blocks
        top_users              = top_users,
        avg_side_effects       = avg_side_effects,
        most_effects_drug      = most_effects_drug,
        most_searched_drug     = most_searched_drug,
    )

# ─────────────────────────────────────────────────────────────
#  ADD THESE TWO ROUTES to your app/routes.py
#
#  New dependencies — add to requirements.txt:
#    reportlab
#
#  Then install:
#    pip install reportlab
# ─────────────────────────────────────────────────────────────

from flask import make_response, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime


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
        .filter(Drug.name.ilike(f'{q}%'))
        .order_by(Drug.name)
        .limit(8)
        .all()
    )
    return jsonify([d.name for d in results])


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
        drug = Drug.query.filter(Drug.name.ilike(name)).first()
        if drug:
            drugs.append(drug)

    # Check interactions between found drugs
    for i in range(len(drugs)):
        for j in range(i + 1, len(drugs)):
            inter = Interaction.query.filter(
                ((Interaction.drug1_id == drugs[i].id) & (Interaction.drug2_id == drugs[j].id)) |
                ((Interaction.drug1_id == drugs[j].id) & (Interaction.drug2_id == drugs[i].id))
            ).first()
            if inter:
                inter.drug1_name = drugs[i].name
                inter.drug2_name = drugs[j].name
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
            story.append(Paragraph(drug.name, h3_style))
            story.append(Paragraph(
                f"<b><font color='#03e9f4'>Indication:</font></b>  {drug.condition or 'Not available'}",
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
        db.session.query(Drug.condition)
        .filter(Drug.condition.ilike(f'%{q}%'))
        .distinct()
        .order_by(Drug.condition)
        .limit(8)
        .all()
    )
    return jsonify([r.condition for r in results if r.condition and r.condition != 'N/A'])