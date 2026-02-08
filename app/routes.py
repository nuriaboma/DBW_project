from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user, login_required
from app import app, db
from app.models import User, Drug, Interaction

# --- HELPER FUNCTION (Your existing logic) ---
def analyze_medications(meds_text):
    if not meds_text: return [], {}
    input_names = [m.strip().lower() for m in meds_text.split(',') if m.strip()]
    found_drugs = []
    side_effects_map = {}
    warnings = []

    for name in input_names:
        drug = Drug.query.filter(Drug.name.ilike(name)).first()
        if drug:
            found_drugs.append(drug)
            effects = [se.effect for se in drug.side_effects[:10]]
            side_effects_map[drug.name] = effects if effects else ["No data"]
    
    for i in range(len(found_drugs)):
        for j in range(i + 1, len(found_drugs)):
            d1, d2 = found_drugs[i], found_drugs[j]
            interaction = Interaction.query.filter(
                ((Interaction.drug1_id == d1.id) & (Interaction.drug2_id == d2.id)) |
                ((Interaction.drug1_id == d2.id) & (Interaction.drug2_id == d1.id))
            ).first()
            if interaction:
                warnings.append({'drug1': d1.name, 'drug2': d2.name, 
                                 'severity': interaction.severity, 'description': interaction.description})
    return warnings, side_effects_map

# --- ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('register'))
            
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid email or password.')
            return redirect(url_for('login'))
            
        login_user(user)
        return redirect(url_for('home'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        age = request.form.get('age')
        condition = request.form.get('condition')
        medications = request.form.get('medications')
        
        warnings_list, side_effects_dict = analyze_medications(medications)
        
        return render_template('result.html', 
                               age=age, condition=condition, medications=medications, 
                               warnings=warnings_list, side_effects=side_effects_dict)

    return render_template('home.html')