import pandas as pd
import os
from app import app, db
from app.models import Drug, Interaction, SideEffect

def clean_col_name(name):
    """Utility: cleans column names to be snake_case."""
    return name.strip().lower().replace(' ', '_').replace('-', '_')

def find_file(base_dir, keywords):
    """Searches for a file in base_dir containing specific keywords."""
    if not os.path.exists(base_dir): return None
    files = os.listdir(base_dir)
    # Exact match
    for k in keywords:
        if k in files: return os.path.join(base_dir, k)
    # Fuzzy match
    for f in files:
        for k in keywords:
            if k.lower() in f.lower() and f.endswith('.csv'):
                return os.path.join(base_dir, f)
    return None

def import_csv_to_db():
    base_dir = 'data'
    
    # 1. Locate Files
    drug_file = find_file(base_dir, ['drug.csv', 'drugs.csv', 'real_drug.csv'])
    inter_file = find_file(base_dir, ['interactions.csv', 'drug_drug_inter.csv'])
    reactions_file = find_file(base_dir, ['drug_reaction.csv', 'drug_reactions.csv', 'reactions.csv'])

    with app.app_context():
        print("--- STARTING FINAL IMPORT ---")
        
        # RESET DATABASE
        db.drop_all()
        db.create_all()
        print("Database schema reset.")

        # ==========================================
        # 1. LOAD DRUGS
        # ==========================================
        all_drugs_map = {} # Cache for IDs

        if drug_file:
            print(f"\nReading {drug_file}...")
            try: df = pd.read_csv(drug_file)
            except: df = pd.read_csv(drug_file, sep=';')
            
            df.columns = [clean_col_name(c) for c in df.columns]
            
            # Try to find name column
            name_col = next((c for c in df.columns if c in ['name', 'drug', 'drug_name', 'generic_name']), None)

            if name_col:
                new_drugs = []
                existing = set()
                
                # Loop through the CSV
                for name in df[name_col].dropna().unique():
                    clean_name = str(name).strip()
                    # Only add if valid
                    if len(clean_name) > 1 and clean_name.lower() not in existing:
                        new_drugs.append(Drug(name=clean_name))
                        existing.add(clean_name.lower())
                
                db.session.add_all(new_drugs)
                db.session.commit()
                print(f"Drugs imported: {len(new_drugs)}")
                
                # Update Cache
                all_drugs_map = {d.name.lower(): d.id for d in Drug.query.all()}
            else:
                print(f"ERROR: No name column in {drug_file}")
        else:
            print("ERROR: Drug file not found.")

        # ==========================================
        # 2. LOAD INTERACTIONS
        # ==========================================
        if inter_file:
            print(f"\nReading {inter_file}...")
            try: df = pd.read_csv(inter_file)
            except: df = pd.read_csv(inter_file, sep=';')
            
            df.columns = [clean_col_name(c) for c in df.columns]
            col_d1, col_d2, col_level = 'drug_a', 'drug_b', 'level'

            interactions = []
            if col_d1 in df.columns and col_d2 in df.columns:
                for _, row in df.iterrows():
                    d1 = str(row[col_d1]).strip().lower()
                    d2 = str(row[col_d2]).strip().lower()
                    if d1 in all_drugs_map and d2 in all_drugs_map:
                        sev = str(row[col_level]) if col_level in df.columns else "Unknown"
                        interactions.append(Interaction(
                            drug1_id=all_drugs_map[d1], 
                            drug2_id=all_drugs_map[d2], 
                            severity=sev, 
                            description=f"Interaction Level: {sev}"
                        ))
                db.session.add_all(interactions)
                db.session.commit()
                print(f"Interactions imported: {len(interactions)}")

        # ==========================================
        # 3. LOAD SIDE EFFECTS (The Fix)
        # ==========================================
        if reactions_file:
            print(f"\nReading {reactions_file}...")
            try: df = pd.read_csv(reactions_file)
            except: df = pd.read_csv(reactions_file, sep=';')
            
            df.columns = [clean_col_name(c) for c in df.columns]
            
            # --- HARDCODED COLUMNS FROM YOUR LOG ---
            col_drug = 'generic_name'
            col_effect = 'reactionmeddrapt_list'

            if col_drug in df.columns and col_effect in df.columns:
                print(f"Mapping: Drug='{col_drug}', EffectList='{col_effect}'")
                
                effects_list = []
                count = 0
                
                for _, row in df.iterrows():
                    # 1. Identify Drug
                    d_name = str(row[col_drug]).strip().lower()
                    
                    if d_name in all_drugs_map:
                        # 2. Process the list of reactions
                        # Assuming format is "Nausea; Vomiting; Headache" or similar
                        raw_effects = str(row[col_effect])
                        
                        # Split by semicolon or comma
                        if ';' in raw_effects:
                            parts = raw_effects.split(';')
                        else:
                            parts = [raw_effects] # Take as is
                        
                        # Add each effect separately
                        for effect in parts:
                            clean_effect = effect.strip()
                            if clean_effect and len(clean_effect) < 200:
                                effects_list.append(SideEffect(
                                    drug_id=all_drugs_map[d_name],
                                    effect=clean_effect
                                ))
                                count += 1
                
                # Bulk save
                db.session.add_all(effects_list)
                db.session.commit()
                print(f"SUCCESS: {count} side effects imported!")
            else:
                print(f"ERROR: Columns '{col_drug}' or '{col_effect}' missing.")
        else:
            print("ERROR: Reactions file not found.")

if __name__ == "__main__":
    import_csv_to_db()