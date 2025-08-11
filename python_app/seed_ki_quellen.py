from models import Session, Quelle

ki_links = [
    ("https://kingkalli.de/events/", "Aachen")
]

session = Session()
inserted = 0

for url, stadt in ki_links:
    if not session.query(Quelle).filter_by(url=url).first():
        q = Quelle(
            name="KI Quelle",
            url=url,
            typ="html",
            stadt=stadt,
            aktiv=True,
            status="pending"
        )
        session.add(q)
        inserted += 1

session.commit()
session.close()
print(f"✅ {inserted} Quellen gespeichert.")
