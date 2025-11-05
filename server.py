from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, MetaData, Table
from sqlalchemy.orm import sessionmaker
import time, random, asyncio

app = FastAPI(title="UAV Collision Server")

# قاعدة البيانات SQLite
engine = create_engine("sqlite:///uav_db.sqlite", connect_args={"check_same_thread": False})
metadata = MetaData()

uav_table = Table(
    "uavs", metadata,
    Column("uav_id", Integer, primary_key=True),
    Column("city_name", String, index=True),
    Column("altitude", Float),
    Column("speed", Float),
    Column("x", Float),
    Column("y", Float)
)

metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

class UAV(BaseModel):
    uav_id: int
    altitude: float
    speed: float
    x: float
    y: float

@app.put("/city/{city}/uav")
async def put_uav(city: str, data: UAV):
    session = SessionLocal()
    try:
        existing = session.query(uav_table).filter_by(city_name=city, uav_id=data.uav_id).first()
        if existing:
            stmt = uav_table.update().where(
                (uav_table.c.city_name==city) & (uav_table.c.uav_id==data.uav_id)
            ).values(altitude=data.altitude, speed=data.speed, x=data.x, y=data.y)
            session.execute(stmt)
        else:
            stmt = uav_table.insert().values(
                city_name=city, uav_id=data.uav_id,
                altitude=data.altitude, speed=data.speed, x=data.x, y=data.y
            )
            session.execute(stmt)
        session.commit()
        await asyncio.sleep(random.uniform(0.002, 0.008))
        return {"status": "ok"}
    finally:
        session.close()

@app.get("/city/{city}/status")
async def get_status(city: str):
    session = SessionLocal()
    try:
        uavs = session.query(uav_table).filter_by(city_name=city).all()
        return {"connected_uavs": len(uavs)}
    finally:
        session.close()
