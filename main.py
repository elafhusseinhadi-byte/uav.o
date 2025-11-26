from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import sessionmaker, declarative_base
from math import sqrt, atan2, cos, sin, pi
import random

# =====================================================
# Config
# =====================================================
CITIES = ["Baghdad", "Basra"]

X_MIN, X_MAX = 33.0, 33.6
Y_MIN, Y_MAX = 44.1, 44.7

STEP_SCALE = 0.00012
COLLISION_THRESHOLD = 0.05
NEAR_FACTOR = 2

# =====================================================
# DB Setup
# =====================================================
engine = create_engine("sqlite:///multicity.sqlite",
                       connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()


class UAV(Base):
    __tablename__ = "uavs"

    uav_id      = Column(Integer, primary_key=True)
    city        = Column(String)     # Baghdad or Basra
    x           = Column(Float)
    y           = Column(Float)
    altitude    = Column(Float)
    speed       = Column(Float)
    direction   = Column(Float)
    system_case = Column(String)     # normal / avoidance / transfer
    target_city = Column(String)
    progress    = Column(Float)

Base.metadata.create_all(engine)

app = FastAPI()


# =====================================================
# Pydantic Model
# =====================================================
class UAVInput(BaseModel):
    uav_id: int
    x: float
    y: float
    altitude: float
    speed: float
    system_case: str = "normal"
    target_city: str | None = None
    progress: float = 0


# =====================================================
# Helper functions
# =====================================================
def dist3(u1, u2):
    return sqrt(
        (u1.x - u2.x)**2 +
        (u1.y - u2.y)**2 +
        ((u1.altitude - u2.altitude)/100)**2
    )

def clamp_position(u):
    u.x = min(max(u.x, X_MIN), X_MAX)
    u.y = min(max(u.y, Y_MIN), Y_MAX)


# =====================================================
# RESET
# =====================================================
@app.delete("/reset")
def reset_all():
    s = Session()
    s.query(UAV).delete()
    s.commit()
    return {"reset": True}


# =====================================================
# UPLOAD to city
# =====================================================
@app.put("/city/{city}/uav")
def put_uav(city: str, u: UAVInput):
    if city not in CITIES:
        return {"error": "unknown city"}

    s = Session()
    r = s.query(UAV).filter(UAV.uav_id == u.uav_id).first()

    if not r:
        r = UAV(
            uav_id=u.uav_id,
            city=city,
            x=u.x, y=u.y,
            altitude=u.altitude,
            speed=u.speed,
            direction=random.uniform(-pi, pi),
            system_case=u.system_case,
            target_city=u.target_city,
            progress=u.progress,
        )
        s.add(r)
    else:
        r.city = city
        r.x = u.x
        r.y = u.y
        r.altitude = u.altitude
        r.speed = u.speed
        r.system_case = u.system_case
        r.target_city = u.target_city
        r.progress = u.progress

    s.commit()
    return {"ok": True}


# =====================================================
# LIST UAVs in City
# =====================================================
@app.get("/city/{city}/uavs")
def get_city(city: str):
    if city not in CITIES:
        return {"uavs": []}
    s = Session()
    rows = s.query(UAV).filter(UAV.city == city).all()
    return {"uavs": [{
        "uav_id": r.uav_id,
        "city": r.city,
        "x": r.x,
        "y": r.y,
        "altitude": r.altitude,
        "speed": r.speed,
        "direction": r.direction,
        "system_case": r.system_case,
        "target_city": r.target_city,
        "progress": r.progress
    } for r in rows]}


# =====================================================
# TRANSFER Baghdad → Basra
# =====================================================
@app.post("/transfer")
def transfer_uav(req: dict):
    uav_id = req["uav_id"]
    from_city = req["from_city"]
    to_city = req["to_city"]

    s = Session()
    row = s.query(UAV).filter(UAV.uav_id == uav_id).first()
    if not row:
        return {"error": "not found"}

    row.system_case = "transfer"
    row.target_city = to_city
    row.progress = 0.0

    s.commit()
    return {"transfer": True}


# =====================================================
# PROCESS movement
# =====================================================
@app.post("/city/{city}/process")
def process_city(city: str):

    s = Session()
    rows = s.query(UAV).filter(UAV.city == city).all()

    # -------- 1) Normal movement --------
    for u in rows:
        if u.system_case == "transfer":
            # linear traveling progress
            u.progress += 0.07

            # Move in straight line toward Basra (example)
            u.x += STEP_SCALE * u.speed
            u.y += STEP_SCALE * u.speed

            if u.progress >= 1.0:
                # move UAV officially to Basra
                u.city = u.target_city
                u.system_case = "normal"

        else:
            # Normal random movement inside city
            u.direction = random.uniform(-pi, pi)
            u.x += u.speed * STEP_SCALE * cos(u.direction)
            u.y += u.speed * STEP_SCALE * sin(u.direction)

        clamp_position(u)

    # -------- 2) Avoidance (simple) --------
    # (يمكن تحديثه إلى B+C مثل جزءك)
    for i in range(len(rows)):
        for j in range(i+1, len(rows)):
            u1 = rows[i]
            u2 = rows[j]

            d = dist3(u1, u2)

            if d < COLLISION_THRESHOLD * NEAR_FACTOR:
                ang = atan2(u2.y - u1.y, u2.x - u1.x)

                # opposite directions
                u1.direction = ang - pi/2
                u2.direction = ang + pi/2

                # slow down slightly
                u1.speed *= 0.85
                u2.speed *= 0.85

                u1.x += 0.02 * cos(u1.direction)
                u1.y += 0.02 * sin(u1.direction)

                u2.x += 0.02 * cos(u2.direction)
                u2.y += 0.02 * sin(u2.direction)

                u1.system_case = "avoidance"
                u2.system_case = "avoidance"

                clamp_position(u1)
                clamp_position(u2)

    s.commit()

    return {"processed": len(rows)}

