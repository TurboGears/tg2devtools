from ming import Session
from ming.odm import ThreadLocalORMSession

mainsession = Session()
DBSession = ThreadLocalORMSession(mainsession)