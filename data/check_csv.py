import pandas as pd

# Versuche die Dateien zu lesen
files = ['patient_drug_reaction.csv', 'patients_final.csv']

for f in files:
    try:
        df = pd.read_csv(f, nrows=2) # Nur die ersten 2 Zeilen lesen
        print(f"\n--- DATEI: {f} ---")
        print("Spalten:", list(df.columns))
    except FileNotFoundError:
        print(f"\n[!] Datei nicht gefunden: {f}")
    except Exception as e:
        print(f"Fehler bei {f}: {e}")
