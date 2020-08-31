import datetime
from contextlib import contextmanager
import sqlalchemy
from sqlalchemy.orm import scoped_session as _scoped_session, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
#from sqlalchemy.orm import relationship
#from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def sql_url_from_config():
    return "sqlite:///duw.sqlite"

def create_engine():
    return sqlalchemy.create_engine(sql_url_from_config(), pool_recycle=600)

engine = create_engine()
_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def scoped_session(expunge=False):
    """Provide a transactional scope around a series of operations.

    If `expunge` is True, the session isn't committed but only closed, which
    expunges (detaches) all objects from the session.
    """
    session = _scoped_session(_session_maker)
    try:
        yield session
        if not expunge:
            session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

default_session = _scoped_session(_session_maker)
Base.query = default_session.query_property()

class RegisterValue(Base):
    __tablename__ = "registers"

    id = Column(Integer, primary_key=True)

    dt = Column(DateTime, default=datetime.datetime.utcnow)
    dev = Column(Integer, index=True)
    reg = Column(Integer, index=True)
    val = Column(Integer)

Base.metadata.create_all(engine)
