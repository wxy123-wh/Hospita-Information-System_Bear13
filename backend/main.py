from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
import logging

# 兼容直接脚本运行（python main.py/uvicorn main:app）与包导入（backend.main）
try:
    from .database import engine, get_db, Base
    from . import models
    from .seed import run as run_seed
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from database import engine, get_db, Base  # type: ignore
    import models  # type: ignore
    from seed import run as run_seed  # type: ignore

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入各模块的路由
from login.backend.routes import router as login_router
from administrator.backend.routes import router as admin_router
from appointments.backend.routes import router as appointments_router
from ai.routes import router as ai_router
from api.auth import router as api_auth_router
from api.admin import router as api_admin_router
from doctor.api import router as api_doctor_router
from api.ai_consult import router as api_ai_consult_router
from api.profile import router as api_profile_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="医疗管理系统API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境请修改为前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_router)
app.include_router(admin_router)
app.include_router(appointments_router)
app.include_router(ai_router)
app.include_router(api_auth_router)
app.include_router(api_admin_router)
app.include_router(api_doctor_router)
app.include_router(api_ai_consult_router)
app.include_router(api_profile_router)

@app.on_event("startup")
def seed_defaults():
    # 让启动流程等价于“迁移+seed”，确保结构和默认账号存在
    run_seed()

@app.get("/")
def read_root():
    return {
        "message": "Medical System API is running",
        "version": "1.0.0",
        "modules": ["login", "administrator", "appointments", "ai", "api.auth", "api.admin", "api.doctor", "api.ai_consult", "api.profile"]
    }

@app.get("/health")
def health():
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Health check failed")
        return JSONResponse(status_code=500, content={"status": "fail", "error": str(e)})

@app.get("/metrics")
def metrics():
    db = next(get_db())
    users = db.query(models.User).count()
    doctors = db.query(models.User).filter(models.User.role == models.UserRole.doctor).count()
    schedules_open = db.query(models.DoctorSchedule).filter(models.DoctorSchedule.status == models.ScheduleStatus.open).count()
    all_schedules = db.query(models.DoctorSchedule).all()
    total_capacity = sum([s.capacity for s in all_schedules])
    total_booked = sum([s.booked_count for s in all_schedules])
    ap_total = db.query(models.Appointment).count()
    ap_confirmed = db.query(models.Appointment).filter(models.Appointment.status == models.AppointmentStatus.confirmed).count()
    ap_cancelled = db.query(models.Appointment).filter(models.Appointment.status == models.AppointmentStatus.cancelled).count()
    return {
        "users": users,
        "doctors": doctors,
        "schedules_open": schedules_open,
        "capacity_total": total_capacity,
        "booked_total": total_booked,
        "appointments": {
            "total": ap_total,
            "confirmed": ap_confirmed,
            "cancelled": ap_cancelled,
        }
    }
# 基础日志配置与请求日志中间件
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger("medical-system")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"{request.method} {request.url.path} -> {response.status_code}")
        return response
    except Exception as e:
        logger.exception(f"Unhandled error on {request.method} {request.url.path}: {e}")
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
