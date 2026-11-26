# ============================================================
#  INSIDER RADAR - PASSO 3: LA MEMORIA + I CLUSTER
#
#  Cosa fa:
#   1. Per ogni giorno lavorativo recente, scarica dalla SEC l'elenco
#      COMPLETO dei Form 4 depositati quel giorno.
#   2. Apre ogni dichiarazione e salva gli ACQUISTI veri (codice P)
#      in un file "acquisti.csv" (si apre anche con Excel/Numbers).
#   3. Si ricorda quali giorni ha gia' fatto ("giorni_fatti.txt"),
#      cosi' la volta dopo scarica solo i giorni nuovi.
#   4. Cerca i CLUSTER: aziende dove piu' persone diverse
#      hanno comprato negli ultimi giorni.
# ============================================================

import csv
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

# ------------------------------------------------------------
#  LE TUE IMPOSTAZIONI (puoi cambiarle quando vuoi)
# ------------------------------------------------------------
def leggi_segreto(nome):
    """Cerca un dato privato prima nei 'Secrets' di GitHub (variabili d'ambiente),
    poi nel file locale segreti.txt (che NON va mai caricato su GitHub)."""
    if os.environ.get(nome):
        return os.environ[nome].strip()
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "segreti.txt")
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8") as f:
            for riga in f:
                if riga.strip().startswith(nome + "="):
                    return riga.split("=", 1)[1].strip().strip('"')
    return ""


# tuo nome + email: li prende da segreti.txt (sul Mac) o dai Secrets (su GitHub)
CHI_SONO = leggi_segreto("SEC_USER_AGENT") or "Mario Rossi mario.rossi@email.com"

GIORNI_INDIETRO = 5      # quanti giorni di calendario guardare indietro
                         # (weekend saltati; ogni giorno lavorativo = ~5-10 minuti!)
FINESTRA_CLUSTER = 14    # un cluster = acquisti entro questi giorni
MIN_PERSONE = 2          # quante persone diverse servono per un cluster
MIN_DOLLARI = 10_000     # sotto questa cifra (per persona) l'acquisto non conta

FILE_ACQUISTI = "acquisti.csv"
FILE_GIORNI = "giorni_fatti.txt"
# ------------------------------------------------------------

COLONNE = ["data_deposito", "data_operazione", "ticker", "azienda",
           "persona", "ruolo", "azioni", "prezzo", "valore", "pratica"]


# ======================  SCARICARE  ==========================

def scarica(url):
    richiesta = urllib.request.Request(url, headers={"User-Agent": CHI_SONO})
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        dati = risposta.read()
    time.sleep(0.12)  # la SEC vuole al massimo 10 richieste al secondo
    return dati


def form4_del_giorno(giorno):
    """Restituisce l'elenco dei Form 4 depositati in un certo giorno.
    Se quel giorno la SEC era chiusa (weekend/festa) restituisce None."""
    trimestre = (giorno.month - 1) // 3 + 1
    url = (f"https://www.sec.gov/Archives/edgar/daily-index/"
           f"{giorno.year}/QTR{trimestre}/form.{giorno.strftime('%Y%m%d')}.idx")
    try:
        testo = scarica(url).decode("latin-1")
    except Exception:
        return None

    percorsi = []
    visti = set()
    for riga in testo.splitlines():
        pezzi = riga.split()
        if len(pezzi) < 5:
            continue
        tipo, percorso = pezzi[0], pezzi[-1]
        if tipo not in ("4", "4/A") or not percorso.endswith(".txt"):
            continue
        pratica = percorso.rsplit("/", 1)[-1].replace(".txt", "")
        if pratica not in visti:          # ogni Form 4 compare 2 volte
            visti.add(pratica)            # (azienda + persona): ne teniamo 1
            percorsi.append(percorso)
    return percorsi


def testo(nodo, percorso):
    trovato = nodo.find(percorso)
    if trovato is None or trovato.text is None:
        return ""
    return trovato.text.strip()


def numero(nodo, percorso):
    try:
        return float(testo(nodo, percorso))
    except ValueError:
        return 0.0


def acquisti_della_dichiarazione(percorso, giorno):
    """Apre una dichiarazione e restituisce solo gli acquisti (codice P)."""
    tutto = scarica("https://www.sec.gov/Archives/" + percorso).decode("utf-8", errors="ignore")
    inizio = tutto.find("<ownershipDocument")
    fine = tutto.find("</ownershipDocument>")
    if inizio == -1 or fine == -1:
        return []
    doc = ET.fromstring(tutto[inizio:fine + len("</ownershipDocument>")])

    azienda = testo(doc, "issuer/issuerName")
    ticker = testo(doc, "issuer/issuerTradingSymbol").upper()
    persona = testo(doc, "reportingOwner/reportingOwnerId/rptOwnerName")
    ruolo = testo(doc, "reportingOwner/reportingOwnerRelationship/officerTitle")
    if not ruolo:
        if testo(doc, "reportingOwner/reportingOwnerRelationship/isDirector") in ("1", "true"):
            ruolo = "Director"
        elif testo(doc, "reportingOwner/reportingOwnerRelationship/isTenPercentOwner") in ("1", "true"):
            ruolo = "Azionista >10%"
        else:
            ruolo = "-"

    pratica = percorso.rsplit("/", 1)[-1].replace(".txt", "")
    risultati = []
    for op in doc.findall("nonDerivativeTable/nonDerivativeTransaction"):
        if testo(op, "transactionCoding/transactionCode") != "P":
            continue
        azioni = numero(op, "transactionAmounts/transactionShares/value")
        prezzo = numero(op, "transactionAmounts/transactionPricePerShare/value")
        risultati.append({
            "data_deposito": giorno.isoformat(),
            "data_operazione": testo(op, "transactionDate/value")[:10],
            "ticker": ticker,
            "azienda": azienda,
            "persona": persona,
            "ruolo": ruolo,
            "azioni": round(azioni),
            "prezzo": round(prezzo, 4),
            "valore": round(azioni * prezzo),
            "pratica": pratica,
        })
    return risultati


# ======================  MEMORIA  ============================

def giorni_gia_fatti():
    if not os.path.exists(FILE_GIORNI):
        return set()
    with open(FILE_GIORNI) as f:
        return {riga.strip() for riga in f if riga.strip()}


def segna_giorno_fatto(giorno):
    with open(FILE_GIORNI, "a") as f:
        f.write(giorno.isoformat() + "\n")


def salva_acquisti(righe):
    nuovo_file = not os.path.exists(FILE_ACQUISTI)
    with open(FILE_ACQUISTI, "a", newline="", encoding="utf-8") as f:
        scrittore = csv.DictWriter(f, fieldnames=COLONNE)
        if nuovo_file:
            scrittore.writeheader()
        scrittore.writerows(righe)


def leggi_acquisti():
    if not os.path.exists(FILE_ACQUISTI):
        return []
    with open(FILE_ACQUISTI, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def aggiorna_memoria():
    fatti = giorni_gia_fatti()
    oggi = date.today()
    # dal giorno piu' vecchio al piu' recente; oggi escluso (la SEC
    # pubblica l'elenco completo di un giorno solo la sera/notte)
    for indietro in range(GIORNI_INDIETRO, 0, -1):
        giorno = oggi - timedelta(days=indietro)
        if giorno.isoformat() in fatti or giorno.weekday() >= 5:
            continue

        print(f"\n📅 {giorno}: scarico l'elenco dei Form 4...")
        percorsi = form4_del_giorno(giorno)
        if percorsi is None:
            print("   elenco non disponibile (festa, o non ancora pubblicato). Salto.")
            continue
        print(f"   {len(percorsi)} dichiarazioni da aprire. Pazienza...")

        trovati = []
        errori = 0
        for i, percorso in enumerate(percorsi, start=1):
            try:
                trovati.extend(acquisti_della_dichiarazione(percorso, giorno))
            except Exception:
                errori += 1  # una dichiarazione illeggibile non blocca tutto
            if i % 100 == 0:
                print(f"   ...{i}/{len(percorsi)} (acquisti trovati finora: {len(trovati)})")

        # Se la SEC ci ha bloccato (troppi errori), NON segniamo il giorno come fatto:
        # cosi' la prossima volta riproviamo invece di perdere quel giorno.
        if percorsi and errori > len(percorsi) / 2:
            print(f"   ⚠️ Troppi errori ({errori}/{len(percorsi)}): la SEC forse ci blocca. "
                  "Non salvo questo giorno, riprovero' la prossima volta.")
            continue

        salva_acquisti(trovati)
        segna_giorno_fatto(giorno)
        print(f"   ✅ Fatto: {len(trovati)} acquisti salvati.")


# ======================  CLUSTER  ============================

def trova_cluster():
    righe = leggi_acquisti()
    limite = (date.today() - timedelta(days=FINESTRA_CLUSTER)).isoformat()

    # raggruppiamo: azienda -> persona -> dollari spesi in totale
    aziende = {}
    for r in righe:
        if r["data_operazione"] < limite or not r["ticker"]:
            continue
        a = aziende.setdefault(r["ticker"], {"nome": r["azienda"], "persone": {}})
        p = a["persone"].setdefault(r["persona"], {"ruolo": r["ruolo"], "valore": 0})
        p["valore"] += float(r["valore"])

    cluster = []
    for ticker, a in aziende.items():
        persone_valide = {n: p for n, p in a["persone"].items() if p["valore"] >= MIN_DOLLARI}
        if len(persone_valide) >= MIN_PERSONE:
            totale = sum(p["valore"] for p in persone_valide.values())
            cluster.append((ticker, a["nome"], persone_valide, totale))

    cluster.sort(key=lambda c: (len(c[2]), c[3]), reverse=True)

    print("\n" + "=" * 70)
    print(f"🎯 CLUSTER BUY degli ultimi {FINESTRA_CLUSTER} giorni "
          f"(almeno {MIN_PERSONE} persone, almeno {MIN_DOLLARI:,} $ a testa)")
    print("=" * 70)
    if not cluster:
        print("Nessun cluster per ora. Normale se hai pochi giorni di dati: riprova domani!")
    for ticker, nome, persone, totale in cluster:
        print(f"\n{ticker}  {nome}  ->  {len(persone)} persone, {totale:,.0f} $ in totale")
        for n, p in sorted(persone.items(), key=lambda x: -x[1]["valore"]):
            print(f"     - {n[:30]:<30} ({p['ruolo'][:25]})  {p['valore']:>12,.0f} $")

    print(f"\n(In memoria ci sono {len(righe)} acquisti in totale. Li trovi in {FILE_ACQUISTI})")


if __name__ == "__main__":
    # salviamo i file nella stessa cartella dello script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    aggiorna_memoria()
    trova_cluster()
