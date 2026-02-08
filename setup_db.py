from app import app, db, models

# Create some dummy data to test RXInsight
def create_sample_data():
    with app.app_context():
        # 1. Clear everything (start fresh)
        db.drop_all()
        db.create_all()

        print("Creating drugs...")
        # Create Drugs
        aspirin = models.Drug(name="Aspirin")
        ibuprofen = models.Drug(name="Ibuprofen")
        warfarin = models.Drug(name="Warfarin")
        lisinopril = models.Drug(name="Lisinopril")

        # Add to session
        db.session.add_all([aspirin, ibuprofen, warfarin, lisinopril])
        db.session.commit()

        print("Creating interactions...")
        # Interaction 1: Aspirin + Warfarin (Dangerous!)
        int_1 = models.Interaction(
            drug1_id=aspirin.id,
            drug2_id=warfarin.id,
            severity="High",
            description="CRITICAL: Increased risk of severe bleeding. Concurrent use requires strict monitoring."
        )

        # Interaction 2: Aspirin + Ibuprofen (Bad for stomach)
        int_2 = models.Interaction(
            drug1_id=aspirin.id,
            drug2_id=ibuprofen.id,
            severity="Medium",
            description="May reduce the heart-protecting effect of Aspirin and increase stomach issues."
        )

        db.session.add_all([int_1, int_2])
        db.session.commit()
        
        print("Database initialized successfully with sample data!")

if __name__ == "__main__":
    create_sample_data()
