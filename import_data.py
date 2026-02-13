import pandas as pd
import os
from app import app, db
from app.models import Drug, Interaction, SideEffect

# Helper to get ID or create drug on the fly
def get_or_create_drug(name, all_drugs_map):
    if not name or str(name).lower() == 'nan':
        return None
    
    name_clean = str(name).strip()
    name_lower = name_clean.lower()
    
    # 1. Fast look-up in memory
    if name_lower in all_drugs_map:
        return all_drugs_map[name_lower]
    
    # 2. Database look-up (case insensitive)
    drug = Drug.query.filter(Drug.name.ilike(name_clean)).first()
    if drug:
        all_drugs_map[name_lower] = drug.id
        return drug.id
    
    # 3. Create if it doesn't exist
    new_drug = Drug(name=name_clean.title(), condition="N/A")
    db.session.add(new_drug)
    db.session.commit() 
    all_drugs_map[name_lower] = new_drug.id
    return new_drug.id

def import_csv_to_db():
    base_dir = 'data'
    # List of all files that might contain drug and side effect data
    drug_sources = ['patient_drug_reaction.csv', 'drug.csv', 'drug_reaction.csv']
    inter_file = os.path.join(base_dir, 'interactions.csv')

    with app.app_context():
        print("--- STARTING DATABASE IMPORT ---")
        db.create_all()
        
        all_drugs_map = {d.name.lower(): d.id for d in Drug.query.all()}
        existing_effects = set((e.drug_id, e.effect) for e in SideEffect.query.all())

        # 1. IMPORT DRUGS & SIDE EFFECTS FROM MULTIPLE SOURCES
        for source in drug_sources:
            file_path = os.path.join(base_dir, source)
            if os.path.exists(file_path):
                print(f"Processing source: {source}...")
                df = pd.read_csv(file_path, nrows=5000)
                
                # We need to find the right column names as they might differ
                cols = df.columns.tolist()
                name_col = next((c for c in cols if 'name' in c.lower() or 'drug' in c.lower()), None)
                effect_col = next((c for c in cols if 'reaction' in c.lower() or 'effect' in c.lower()), None)

                if name_col and effect_col:
                    for _, row in df.iterrows():
                        d_id = get_or_create_drug(row[name_col], all_drugs_map)
                        reaction = str(row[effect_col]).strip()
                        
                        if d_id and reaction and (d_id, reaction) not in existing_effects:
                            db.session.add(SideEffect(drug_id=d_id, effect=reaction))
                            existing_effects.add((d_id, reaction))
                    db.session.commit()
                else:
                    print(f"Skipping {source}: Could not detect name or effect columns.")

        # 2. IMPORT INTERACTIONS
        if os.path.exists(inter_file):
            print("Importing Interactions...")
            df_inter = pd.read_csv(inter_file)
            count_inter = 0
            
            for _, row in df_inter.iterrows():
                id1 = get_or_create_drug(str(row['Drug_A']), all_drugs_map)
                id2 = get_or_create_drug(str(row['Drug_B']), all_drugs_map)
                
                if id1 and id2 and id1 != id2:
                    exists = Interaction.query.filter_by(drug1_id=id1, drug2_id=id2).first()
                    if not exists:
                        db.session.add(Interaction(
                            drug1_id=id1, 
                            drug2_id=id2, 
                            description=f"Risk Level: {row.get('Level', 'Unknown')}"
                        ))
                        count_inter += 1
            
            db.session.commit()
            print(f"--- SUCCESS: Added {count_inter} interactions ---")

if __name__ == "__main__":
    import_csv_to_db()