from ming import Session
from ming.orm import ThreadLocalORMSession

mainsession = Session()
DBSession = ThreadLocalORMSession(mainsession)