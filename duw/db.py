import datetime
from contextlib import contextmanager
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
#from sqlalchemy.orm import relationship
#from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def sql_url_from_config():
    return "sqlite://"

def create_engine():
    return sqlalchemy.create_engine(sql_url_from_config(), pool_recycle=600)

engine = create_engine()
Session = sqlalchemy.orm.sessionmaker(bind=engine)

# From: http://docs.sqlalchemy.org/en/latest/orm/session_basics.html
# I wonder why this is not built in ...
@contextmanager
def session_scope(expunge=False):
    """Provide a transactional scope around a series of operations.

    If `expunge` is True, the session isn't committed but only closed, which
    expunges (detaches) all objects from the session.
    """
    session = Session()
    try:
        yield session
        if not expunge:
            session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


class RegisterValue(Base):
    __tablename__ = "registers"

    id = Column(Integer, primary_key=True)

    dt = Column(DateTime, default=datetime.datetime.utcnow)
    register = Column(Integer, index=True)
    value = Column(Integer, index=True)

Base.metadata.create_all(engine)
