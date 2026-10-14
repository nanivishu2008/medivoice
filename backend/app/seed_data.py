from datetime import datetime, timezone, timedelta
from .database import SessionLocal, engine, Base
from .models import Doctor, AppointmentSlot


def seed_database():
    """
    Populates synthetic demonstration doctors and multi-day appointment slots.
    Ensures safe idempotent execution (will not duplicate if doctors already exist).
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing_count = db.query(Doctor).count()
        if existing_count > 0:
            return

        doctors = [
            Doctor(
                name="Dr. Sarah Jenkins",
                specialty="Cardiology",
                qualification="MD, FACC - Harvard Medical School",
                bio="Specialist in preventive cardiology, hypertension, and cardiovascular health management."
            ),
            Doctor(
                name="Dr. Alex Rivera",
                specialty="Dermatology",
                qualification="MD, FAAD - Johns Hopkins University",
                bio="Dermatologist focusing on skin cancer screening, eczema management, and acne therapies."
            ),
            Doctor(
                name="Dr. Priya Sharma",
                specialty="General Practice",
                qualification="MBBS, MRCGP - Oxford University",
                bio="Family physician dedicated to comprehensive preventive wellness and chronic illness care."
            ),
            Doctor(
                name="Dr. Michael Chang",
                specialty="Pediatrics",
                qualification="MD, FAAP - Stanford University",
                bio="Compassionate pediatrician providing developmental and acute pediatric care for all ages."
            )
        ]

        db.add_all(doctors)
        db.commit()

        # Seed appointment slots over the next 5 days
        now = datetime.now(timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)
        slots = []

        # Generate slots for Day 1 through Day 5
        slot_hours = [9, 10, 11, 14, 15, 16]  # 9 AM, 10 AM, 11 AM, 2 PM, 3 PM, 4 PM

        for day_offset in range(1, 6):
            target_date = now + timedelta(days=day_offset)
            for doctor in doctors:
                for hour in slot_hours:
                    start_dt = target_date.replace(hour=hour, minute=0)
                    end_dt = start_dt + timedelta(minutes=45)
                    slots.append(
                        AppointmentSlot(
                            doctor_id=doctor.id,
                            start_time=start_dt,
                            end_time=end_dt,
                            is_booked=False
                        )
                    )

        db.add_all(slots)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
