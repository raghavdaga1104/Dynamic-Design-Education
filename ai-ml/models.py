from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)

    name = Column(String, nullable=False)

    password_hash = Column(String, nullable=False)

    salt = Column(String, nullable=False)

    degree = Column(String, default="BTech")

    year = Column(String, default="2nd")

    interest = Column(String, default="python")

    user_id = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )