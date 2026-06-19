from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    user_id = Column(String, unique=True, nullable=False, index=True)

    name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False, index=True)

    password_hash = Column(String, nullable=False)

    salt = Column(String, nullable=False)

    degree = Column(String, default="BTech")

    year = Column(String, default="2nd")

    interest = Column(String, default="python")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )