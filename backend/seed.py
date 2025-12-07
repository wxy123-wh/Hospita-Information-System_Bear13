"""
Minimal seed script to sync the schema and ensure default accounts/schedules exist.

Usage:
    # from repo root
    cd backend
    python -m seed
"""
from datetime import date, timedelta, time
from passlib.context import CryptContext

try:
    from .database import engine, SessionLocal, Base
    from . import models
except ImportError:
    from database import engine, SessionLocal, Base  # type: ignore
    import models  # type: ignore


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(password: str) -> str:
    return pwd_context.hash(password)


def _ensure_default_users(session):
    """Create baseline admin/doctor/pharmacist/patient accounts if missing."""
    defaults = [
        {
            "phone": "13800138000",
            "password": "admin",
            "role": models.UserRole.admin,
            "status": models.UserStatus.active,
        },
        {
            "phone": "13900000000",
            "password": "doctor",
            "role": models.UserRole.doctor,
            "status": models.UserStatus.active,
            "profile": {
                "name": "示例医生",
                "department": "内科",
                "title": "主治医师",
                "hospital": "示例医院",
            },
        },
        {
            "phone": "13700000000",
            "password": "pharmacist",
            "role": models.UserRole.pharmacist,
            "status": models.UserStatus.active,
        },
        {
            "phone": "13600000000",
            "password": "patient",
            "role": models.UserRole.user,
            "status": models.UserStatus.active,
        },
    ]

    for item in defaults:
        user = session.query(models.User).filter(models.User.phone == item["phone"]).first()
        if user:
            continue
        user = models.User(
            phone=item["phone"],
            password=_hash(item["password"]),
            role=item["role"],
            status=item["status"],
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Attach doctor profile when needed
        if item.get("profile") and item["role"] == models.UserRole.doctor:
            profile_data = item["profile"]
            profile = models.DoctorProfile(user_id=user.id, **profile_data)
            session.add(profile)
            session.commit()

        # Ensure a basic patient profile exists for users
        if item["role"] == models.UserRole.user:
            patient_profile = models.PatientProfile(user_id=user.id, name="示例患者")
            session.add(patient_profile)
            session.commit()

    return session.query(models.User).filter(models.User.role == models.UserRole.doctor).first()


def _ensure_doctor_schedules(session, doctor):
    """Prepare one week of open AM/PM schedules plus day aggregates."""
    today = date.today()
    for offset in range(0, 7):
        d = today + timedelta(days=offset)
        for start, end, is_am in [
            (time(9, 0), time(12, 0), True),
            (time(13, 0), time(17, 0), False),
        ]:
            exists = session.query(models.DoctorSchedule).filter(
                models.DoctorSchedule.doctor_id == doctor.id,
                models.DoctorSchedule.date == d,
                models.DoctorSchedule.start_time == start,
            ).first()
            if not exists:
                schedule = models.DoctorSchedule(
                    doctor_id=doctor.id,
                    date=d,
                    start_time=start,
                    end_time=end,
                    capacity=0,
                    booked_count=0,
                    status=models.ScheduleStatus.open,
                )
                session.add(schedule)

        day = session.query(models.DoctorDaySchedule).filter(
            models.DoctorDaySchedule.doctor_id == doctor.id,
            models.DoctorDaySchedule.date == d,
        ).first()
        if not day:
            day = models.DoctorDaySchedule(
                doctor_id=doctor.id,
                date=d,
                am_capacity=0,
                am_booked_count=0,
                pm_capacity=0,
                pm_booked_count=0,
            )
            session.add(day)
    session.commit()

    # 保持一个月的日聚合表（即便没有具体排班）
    for offset in range(0, 30):
        d = today + timedelta(days=offset)
        day = session.query(models.DoctorDaySchedule).filter(
            models.DoctorDaySchedule.doctor_id == doctor.id,
            models.DoctorDaySchedule.date == d,
        ).first()
        if not day:
            day = models.DoctorDaySchedule(
                doctor_id=doctor.id,
                date=d,
                am_capacity=0,
                am_booked_count=0,
                pm_capacity=0,
                pm_booked_count=0,
            )
            session.add(day)
    session.commit()


def run():
    """Entry point used by startup hook and manual seeding."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        doctor = _ensure_default_users(session)
        if doctor:
            _ensure_doctor_schedules(session, doctor)
    finally:
        session.close()


if __name__ == "__main__":
    run()
