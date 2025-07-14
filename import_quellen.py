# import_quellen.py

import csv
from models import Quelle, Session

with open("quellen.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    session = Session()

    for row in reader:
        quelle = Quelle(
            name=row["name"],
            url=row["url"],
            typ=row["typ"],
            stadt=row["stadt"],
            aktiv=bool(row["aktiv"]),
        )
        session.add(quelle)

    session.commit()
    print("✅ Quellen erfolgreich importiert.")
