# =====================================================
# 🚀 UAV Simulation Server (Online Ready) - Fully Updated
# =====================================================
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
import time, asyncio, random, os

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

metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# -------------------------------
# 🖥️ إعداد FastAPI server
# -------------------------------
app = FastAPI(title="UAV Simulation Server (Online)")

# صفحة رئيسية HTML
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head><title>UAV Simulation</title></head>
      <body>
        <h1>✅ UAV Simulation API is running on Render!</h1>
        <p>JSON API: <a href="/api">/api</a></p>
        <p>Health: <a href="/health">/health</a></p>
        <p>Update all UAVs: <a href="/update_all">/update_all</a></p>
      </body>
    </html>
    """

# -------------------------------
# Health check
# -------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api")
def api_index():
    return {
        "service": "uav-simulation",
        "endpoints": [
            "/city/{city}/uav (PUT)",
            "/city/{city}/uavs (GET)",
            "/city/{city}/process (POST)",
            "/update_all (POST)"
        ]
    }

# -------------------------------
# PUT: إضافة أو تحديث UAV
# -------------------------------
@app.put("/city/{city}/uav")
async def put_uav(city: str, data: UAV):
    start = time.time()
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
# GET: استرجاع UAVs
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
        uav_list = []
        for u in uavs:
            row = dict(u)
            uav_list.append({
                "uav_id": int(row.get("uav_id")),
                "x": float(row.get("x", 0)),
                "y": float(row.get("y", 0)),
                "altitude": float(row.get("altitude", 0)),
                "speed": float(row.get("speed", 0)),
                "system_case": str(row.get("system_case", ""))
            })
        return {"uavs": uav_list, "get_time_ms": round(elapsed_ms, 3)}
    finally:
        session.close()

# -------------------------------
# POST: معالجة (كشف تصادم)
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
        for i in range(n):
            for j in range(i + 1, n):
                dx = float(uavs[i].x) - float(uavs[j].x)
                dy = float(uavs[i].y) - float(uavs[j].y)
                if (dx**2 + dy**2) ** 0.5 < 5:
                    collision_pairs.append([uavs[i].uav_id, uavs[j].uav_id])
        await asyncio.sleep(min(1.0, 0.001 * n))
        elapsed_ms = (time.time() - start) * 1000
        return {
            "processed_uavs": n,
            "collisions_detected": len(collision_pairs),
            "collision_pairs": collision_pairs,
            "post_time_ms": round(elapsed_ms, 3)
        }
    finally:
        session.close()

# -------------------------------
# 🆕 NEW: تحديث جميع بيانات الطائرات (Update All)
# -------------------------------
@app.post("/update_all")
def update_all():
    """يحدّث كل الطائرات في القاعدة بقيم جديدة (مثلاً زيادة السرعة وتغيير الموقع)."""
    session = SessionLocal()
    try:
        uavs = session.query(uav_table).all()
        if not uavs:
            return {"status": "no_data", "message": "لا توجد طائرات لتحديثها."}
        count = 0
        for u in uavs:
            # تحديث القيم بشكل بسيط
            new_x = float(u.x) + random.uniform(-1, 1)
            new_y = float(u.y) + random.uniform(-1, 1)
            new_speed = float(u.speed) * random.uniform(0.9, 1.1)
            stmt = uav_table.update().where(uav_table.c.uav_id == u.uav_id).values(
                x=new_x, y=new_y, speed=new_speed
            )
            session.execute(stmt)
            count += 1
        session.commit()
        return {"status": "updated", "updated_records": count}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# -------------------------------
# 🌍 تشغيل السيرفر محليًا
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
