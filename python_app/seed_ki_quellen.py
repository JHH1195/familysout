from models import Session, Quelle

ki_links = [
    ("https://www.familienbildung-aachen.de/programm/eltern-kind-angebote", "Aachen"),
    ("https://www.hausfuerfamilien-aachen.de/programm/zeit-mit-kindern", "Aachen"),
    ("https://www.heleneweberhaus.de/rubrik_familienleben/", "Aachen"),
    ("https://www.treffpunkt-luise.de/programm/babys-kleinkinder-kinder", "Aachen"),
    ("https://www.kiba-aachen.de/kinderkurse/", "Aachen"),
    ("https://www.kiba-aachen.de/ferienfreizeiten/", "Aachen"),
    ("https://www.vhs-nordkreis-aachen.de/programm/kategorie/Eltern-Kind-Programm/52", "Aachen"),
    ("https://www.musikschule-brand.de/musikalische-frueherziehung/eltern-kind-kurse/", "Aachen"),
    ("https://www.bistum-aachen.de/region-heinsberg/aktuell/nachrichten-buero/a-blog/Eltern-Baby---Eltern-Kind-Kurse-ab-August-2024/", "Aachen"),
    ("https://simonis-beratung.de", "Aachen"),
    ("https://www.marienhospital.de/de/prävention/kursprogramm/eltern-kind-kurse/babysteps-mehr-als-nur-ein-babykurs", "Aachen"),
    ("https://klingwiese.de/musikschule-aachen-kurse/", "Aachen"),
    ("https://www.madamedubidu.com/kurse/", "Aachen"),
    ("https://www.rwth-aachen.de/cms/root/wir/Profil/Familiengerechte-Hochschule/~zvs/Eltern-Kind-Gruppen/", "Aachen"),
    ("https://sportverein-aachen.de/sportart/eltern-kind-turnen/", "Aachen"),
    ("https://www.tv-muetzenich.de/abteilungen/turnen/eltern-kind-turnen/", "Aachen"),
    ("https://tv-konzen.de/turnen/eltern-kind-turnen/", "Aachen"),
    ("https://tv-konzen.de/turnen/kinderturnen/", "Aachen"),
    ("https://kingkalli.de/events/", "Aachen"),
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
