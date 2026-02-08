from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Repariere Datenbank...")
    
    # 1. Lösche die falsche User-Tabelle
    # Wir machen das hart mit SQL, damit sie wirklich weg ist
    try:
        db.session.execute(text('DROP TABLE user'))
        db.session.commit()
        print("-> Alte, falsche User-Tabelle gelöscht.")
    except Exception as e:
        print(f"-> Info: Tabelle konnte nicht gelöscht werden (vielleicht war sie schon weg): {e}")

    # 2. Erstelle die Tabellen neu
    # Da die User-Tabelle jetzt fehlt, wird sie neu (und korrekt!) angelegt
    db.create_all()
    print("-> Neue User-Tabelle (mit iduser) erfolgreich erstellt!")
