# =====================================================
# 🚀 UAV Simulation Server (Online Ready - Cloud Analytics)
# =====================================================
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
import time, random, asyncio
from math import sqrt, cos, sin, pi
import numpy as np

# -------------------------------
# 🛰️ نموذج بيانات UAV
# -------------------------------
class UAV(BaseModel):
    uav_id: int
    x: float
    y: float
    altitude: float
    speed: float
    system_case: str  # normal, avoidance

# -------------------------------
# ⚙️ إعداد قاعدة بيانات SQLite
# -------------------------------
engine = create_engine("sqlite:///uav_db_full.sqlite", connect_args={"check_same_thread": False})
metadata = MetaData()

uav_table = Table(
    "uavs", metadata,
    Column("uav_id", Integer, primary_key=True),
    Column("city_name", String, index=True),
    Column("x", Float),
    Column("y", Float),
    Column("altitude", Float),
    Column("speed", Float),
    Column("system_case", String)
)
metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# -------------------------------
# 🖥️ إعداد FastAPI server
# -------------------------------
app = FastAPI(title="UAV Simulation Server (Online + Cloud Analytics)")

# =====================================================
# 🛰️ رفع بيانات الطائرات (PUT)
# =====================================================
@app.put("/city/{city}/uav")
async def put_uav(city: str, data: UAV):
    session = SessionLocal()
    start = time.time()
    try:
        existing = session.query(uav_table).filter_by(city_name=city, uav_id=data.uav_id).first()
        if existing:
            stmt = uav_table.update().where(
                (uav_table.c.city_name == city) & (uav_table.c.uav_id == data.uav_id)
            ).values(
                x=data.x, y=data.y,
                altitude=data.altitude,
                speed=data.speed,
                system_case=data.system_case
            )
            session.execute(stmt)
        else:
            stmt = uav_table.insert().values(
                city_name=city,
                uav_id=data.uav_id,
                x=data.x,
                y=data.y,
                altitude=data.altitude,
                speed=data.speed,
                system_case=data.system_case
            )
            session.execute(stmt)
        session.commit()
        elapsed_ms = (time.time() - start) * 1000
        return {"status": "ok", "put_time_ms": round(elapsed_ms, 3)}
    finally:
        session.close()

# =====================================================
# 📦 استرجاع بيانات الطائرات (GET)
# =====================================================
@app.get("/city/{city}/uavs")
async def get_uavs(city: str, system_case: str = None):
    session = SessionLocal()
    start = time.time()
    try:
        query = session.query(uav_table).filter_by(city_name=city)
        if system_case:
            query = query.filter_by(system_case=system_case)
        uavs = query.all()
        elapsed_ms = (time.time() - start) * 1000
        approx_db_kb = round(len(uavs) * 0.5, 2)
        return {
            "uavs": [
                {
                    "uav_id": u.uav_id,
                    "x": u.x,
                    "y": u.y,
                    "altitude": u.altitude,
                    "speed": u.speed,
                    "system_case": u.system_case,
                }
                for u in uavs
            ],
            "get_time_ms": round(elapsed_ms, 3),
            "db_size_kb": approx_db_kb,
        }
    finally:
        session.close()

# =====================================================
# ⚙️ معالجة البيانات العادية (POST)
# =====================================================
@app.post("/city/{city}/process")
async def process_uavs(city: str, system_case: str = None):
    session = SessionLocal()
    start = time.time()
    try:
        query = session.query(uav_table).filter_by(city_name=city)
        if system_case:
            query = query.filter_by(system_case=system_case)
        uavs = query.all()
        n = len(uavs)
        collision_pairs = []

        # كشف التصادم (distance < 5)
        for i in range(n):
            for j in range(i + 1, n):
                dx = uavs[i].x - uavs[j].x
                dy = uavs[i].y - uavs[j].y
                if (dx**2 + dy**2) ** 0.5 < 5:
                    collision_pairs.append([uavs[i].uav_id, uavs[j].uav_id])

        # محاكاة زمن المعالجة
        await asyncio.sleep(0.001 * n)
        elapsed_ms = (time.time() - start) * 1000
        avg_per_uav = round(elapsed_ms / n, 3) if n > 0 else 0
        return {
            "processed_uavs": n,
            "post_time_ms": round(elapsed_ms, 3),
            "avg_post_per_uav_ms": avg_per_uav,
            "collisions_detected": len(collision_pairs),
            "collision_pairs": collision_pairs,
        }
    finally:
        session.close()

# =====================================================
# 🤖 تنبؤ التصادمات + تجنّبها (Cloud Analytics)
# =====================================================
@app.post("/city/{city}/predict")
async def predict_and_avoid(city: str):
    session = SessionLocal()
    start = time.time()
    try:
        uavs = session.query(uav_table).filter_by(city_name=city).all()
        n = len(uavs)
        if n == 0:
            return {"message": "No UAVs found for prediction."}

        Δt = 5.0  # زمن التنبؤ (ثوانٍ)
        collision_threshold = 0.05  # مسافة الخطر (درجات تقريباً ~5م)
        collision_pairs = []
        adjusted = []

        # توليد اتجاه عشوائي وسرعة مستقبلية
        for u in uavs:
            angle = random.uniform(0, 2 * pi)
            u.vx = u.speed * cos(angle) / 100
            u.vy = u.speed * sin(angle) / 100
            u.x_future = u.x + u.vx * Δt
            u.y_future = u.y + u.vy * Δt

        # 🔍 التنبؤ بالتصادمات
        for i in range(n):
            for j in range(i + 1, n):
                dist = sqrt(
                    (uavs[i].x_future - uavs[j].x_future) ** 2
                    + (uavs[i].y_future - uavs[j].y_future) ** 2
                )
                if dist < collision_threshold:
                    collision_pairs.append([uavs[i].uav_id, uavs[j].uav_id])
                    # تعديل الارتفاع لتجنّب التصادم
                    uavs[i].altitude += 10
                    uavs[j].altitude -= 10
                    adjusted.append((uavs[i].uav_id, uavs[j].uav_id))

        # تحديث قاعدة البيانات بعد التنبؤ
        for u in uavs:
            stmt = uav_table.update().where(
                (uav_table.c.city_name == city)
                & (uav_table.c.uav_id == u.uav_id)
            ).values(
                x=u.x_future,
                y=u.y_future,
                altitude=u.altitude,
                system_case="avoidance"
                if u.uav_id in sum(collision_pairs, ())
                else "normal",
            )
            session.execute(stmt)
        session.commit()

        elapsed_ms = (time.time() - start) * 1000
        return {
            "processed_uavs": n,
            "predicted_collisions": len(collision_pairs),
            "adjusted_pairs": len(adjusted),
            "collision_pairs": collision_pairs,
            "execution_time_ms": round(elapsed_ms, 2),
        }
    finally:
        session.close()

# =====================================================
# 🌍 تشغيل السيرفر (على Render)
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
