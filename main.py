# =====================================================
# 🚀 UAV Simulation Server (Online Ready) - Updated
# =====================================================
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
import time, asyncio
import os

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
# ⚙️ إعداد قاعدة بيانات SQLite (نسبي - مناسب للـ Render)
# -------------------------------
DB_FILE = os.getenv("UAV_DB_FILE", "uav_db_full.sqlite")
DATABASE_URL = f"sqlite:///./{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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

# أنشئ الجداول لو ما موجودة
metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# -------------------------------
# 🖥️ إعداد FastAPI server
# -------------------------------
app = FastAPI(title="UAV Simulation Server (Online)")

# صفحة رئيسية HTML بسيطة
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head><title>UAV Simulation</title></head>
      <body>
        <h1>✅ UAV Simulation API is running on Render!</h1>
        <p>JSON API: <a href="/api">/api</a></p>
        <p>Health: <a href="/health">/health</a></p>
      </body>
    </html>
    """

# نقطة اختبار سريعة (health)
@app.get("/health")
def health():
    return {"status": "ok"}

# نقطة لمشاهدة بعض المعلومات الأساسية
@app.get("/api")
def api_index():
    return {"service": "uav-simulation", "endpoints": ["/city/{city}/uav (PUT)", "/city/{city}/uavs (GET)", "/city/{city}/process (POST)"]}

# -------------------------------
# PUT: أضف أو حدّث UAV
# -------------------------------
@app.put("/city/{city}/uav")
async def put_uav(city: str, data: UAV):
    start = time.time()
    # استخدم session داخل context manager حتى تُغلق دائماً
    session = SessionLocal()
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
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# -------------------------------
# GET: استرجاع جميع UAVs في مدينة
# -------------------------------
@app.get("/city/{city}/uavs")
async def get_uavs(city: str, system_case: str = None):
    start = time.time()
    session = SessionLocal()
    try:
        query = session.query(uav_table).filter_by(city_name=city)
        if system_case:
            query = query.filter_by(system_case=system_case)
        uavs = query.all()
        elapsed_ms = (time.time() - start) * 1000
        approx_db_kb = round(len(uavs) * 0.5, 2)
        # بناء القائمة بطريقة آمنة
        uav_list = []
        for u in uavs:
            # بعض أنواع نتائج SQLAlchemy قد تكون RowProxy أو كائن؛ حاول الوصول بالاسم أو بالفهرس
            try:
                uav_list.append({
                    "uav_id": int(u.uav_id),
                    "x": float(u.x),
                    "y": float(u.y),
                    "altitude": float(u.altitude),
                    "speed": float(u.speed),
                    "system_case": str(u.system_case)
                })
            except Exception:
                # محاولة بديلة لو كانت النتيجة dict-like
                row = dict(u)
                uav_list.append({
                    "uav_id": int(row.get("uav_id")),
                    "x": float(row.get("x") or 0),
                    "y": float(row.get("y") or 0),
                    "altitude": float(row.get("altitude") or 0),
                    "speed": float(row.get("speed") or 0),
                    "system_case": str(row.get("system_case") or "")
                })

        return {"uavs": uav_list,
                "get_time_ms": round(elapsed_ms, 3),
                "db_size_kb": approx_db_kb}
    finally:
        session.close()

# -------------------------------
# POST: عملية معالجة (مثال: كشف تصادم)
# -------------------------------
@app.post("/city/{city}/process")
async def process_uavs(city: str, system_case: str = None):
    start = time.time()
    session = SessionLocal()
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
                try:
                    dx = float(uavs[i].x) - float(uavs[j].x)
                    dy = float(uavs[i].y) - float(uavs[j].y)
                except Exception:
                    # fallback to dict-like
                    row_i = dict(uavs[i])
                    row_j = dict(uavs[j])
                    dx = float(row_i.get("x", 0)) - float(row_j.get("x", 0))
                    dy = float(row_i.get("y", 0)) - float(row_j.get("y", 0))
                if (dx ** 2 + dy ** 2) ** 0.5 < 5:
                    try:
                        collision_pairs.append([int(uavs[i].uav_id), int(uavs[j].uav_id)])
                    except Exception:
                        ri = dict(uavs[i]); rj = dict(uavs[j])
                        collision_pairs.append([int(ri.get("uav_id")), int(rj.get("uav_id"))])

        # محاكاة زمن المعالجة (بدون حظر طويل)
        if n > 0:
            await asyncio.sleep(min(1.0, 0.001 * n))  # حدود للـ sleep
        elapsed_ms = (time.time() - start) * 1000
        avg_per_uav = round(elapsed_ms / n, 3) if n > 0 else 0
        return {"processed_uavs": n,
                "post_time_ms": round(elapsed_ms, 3),
                "avg_post_per_uav_ms": avg_per_uav,
                "collisions_detected": len(collision_pairs),
                "collision_pairs": collision_pairs}
    finally:
        session.close()

# -------------------------------
# 🌍 تشغيل السيرفر محليًا (مهم فقط عند التشغيل المحلي)
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
