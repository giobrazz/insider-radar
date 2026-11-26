# ============================================================
#  INSIDER RADAR - PASSO 4: PULIZIA + PUNTEGGIO
#
#  NON scarica niente: legge la memoria "acquisti.csv" creata
#  dal passo 3. Quindi prima lanci STEP3.py, poi STEP4.py.
#
#  Cosa fa:
#   1. Toglie il "rumore" (ticker mancanti, fondi, grandi azionisti)
#   2. Trova i cluster, come il passo 3
#   3. Da' a ogni cluster un PUNTEGGIO e spiega il perche'
#   4. Salva la classifica in "cluster.csv" (servira' per Telegram
#      e per la dashboard)
# ============================================================

import csv
import math
import os
from datetime import date, timedelta

# ------------------------------------------------------------
#  LE TUE REGOLE (cambiale quando vuoi)
# ------------------------------------------------------------
FINESTRA_CLUSTER = 14     # acquisti negli ultimi N giorni
MIN_PERSONE = 2           # persone diverse per fare un cluster
MIN_DOLLARI = 10_000      # cifra minima a persona

ESCLUDI_AZIONISTI_10 = False  # togliere i grandi azionisti >10% (es. Blackstone)?
ESCLUDI_FONDI = False         # togliere i fondi d'investimento?
PAROLE_FONDI = ["FUND"]       # se il nome dell'azienda contiene queste parole = fondo

QUANTI_MOSTRARE = 15          # quanti cluster stampare
# ------------------------------------------------------------

FILE_ACQUISTI = "acquisti.csv"
FILE_CLUSTER = "cluster.csv"
TICKER_NON_VALIDI = {"", "NONE", "N/A", "NA", "-"}


def e_ceo(ruolo):
    r = ruolo.upper()
    return "CEO" in r or "CHIEF EXECUTIVE" in r


def e_cfo(ruolo):
    r = ruolo.upper()
    return "CFO" in r or "CHIEF FINANCIAL" in r


def leggi_acquisti():
    if not os.path.exists(FILE_ACQUISTI):
        print(f"Non trovo {FILE_ACQUISTI}: lancia prima STEP3.py!")
        return []
    with open(FILE_ACQUISTI, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ======================  1. PULIZIA  =========================

def pulisci(righe):
    limite = (date.today() - timedelta(days=FINESTRA_CLUSTER)).isoformat()
    tenute, tolte = [], {"vecchie": 0, "ticker": 0, "azionisti_10": 0, "fondi": 0, "doppioni": 0}
    visti = set()
    for r in righe:
        # DOPPIONI: stessa azienda, stesso giorno, stesse azioni, stesso prezzo
        # = quasi sempre la STESSA operazione dichiarata da piu' soggetti collegati
        # (es. una persona + la sua societa'). La contiamo una volta sola.
        impronta = (r["ticker"], r["data_operazione"], r["azioni"], r["prezzo"])
        if impronta in visti:
            tolte["doppioni"] += 1
            continue
        visti.add(impronta)

        if r["data_operazione"] < limite:
            tolte["vecchie"] += 1
        elif r["ticker"].strip().upper() in TICKER_NON_VALIDI:
            tolte["ticker"] += 1
        elif ESCLUDI_AZIONISTI_10 and r["ruolo"] == "Azionista >10%":
            tolte["azionisti_10"] += 1
        elif ESCLUDI_FONDI and any(p in r["azienda"].upper() for p in PAROLE_FONDI):
            tolte["fondi"] += 1
        else:
            tenute.append(r)
    return tenute, tolte


# ======================  2. CLUSTER  =========================

def trova_cluster(righe):
    aziende = {}
    for r in righe:
        a = aziende.setdefault(r["ticker"], {"nome": r["azienda"], "persone": {}})
        p = a["persone"].setdefault(r["persona"], {"ruolo": r["ruolo"], "valore": 0, "date": []})
        p["valore"] += float(r["valore"])
        p["date"].append(r["data_operazione"])

    cluster = []
    for ticker, a in aziende.items():
        persone = {n: p for n, p in a["persone"].items() if p["valore"] >= MIN_DOLLARI}
        if len(persone) >= MIN_PERSONE:
            cluster.append({"ticker": ticker, "azienda": a["nome"], "persone": persone})
    return cluster


# ======================  3. PUNTEGGIO  =======================
#  Massimo 100 punti, diviso in 4 parti:
#   - QUANTE persone        fino a 40 punti (10 a persona)
#   - QUANTI dollari        fino a 30 punti (10k=0, 100k=10, 1M=20, 10M=30)
#   - CHI compra            CEO +15, CFO +10
#   - QUANDO (vicinanza)    tutti entro 5 giorni +5 ... (vedi sotto)
# ------------------------------------------------------------

def dai_punteggio(c):
    persone = c["persone"]
    totale = sum(p["valore"] for p in persone.values())
    tutte_le_date = sorted(d for p in persone.values() for d in p["date"])
    prima, ultima = tutte_le_date[0], tutte_le_date[-1]
    giorni = (date.fromisoformat(ultima) - date.fromisoformat(prima)).days

    punti_persone = min(40, 10 * len(persone))
    punti_dollari = max(0, min(30, 10 * math.log10(max(totale, 1) / 10_000)))
    c_ceo = any(e_ceo(p["ruolo"]) for p in persone.values())
    c_cfo = any(e_cfo(p["ruolo"]) for p in persone.values())
    punti_ruoli = (15 if c_ceo else 0) + (10 if c_cfo else 0)
    punti_tempo = 5 if giorni <= 5 else 0

    c.update({
        "punteggio": round(punti_persone + punti_dollari + punti_ruoli + punti_tempo),
        "totale": totale,
        "n_persone": len(persone),
        "ceo": c_ceo,
        "cfo": c_cfo,
        "prima": prima,
        "ultima": ultima,
        "giorni": giorni,
        "perche": (f"{len(persone)} persone (+{punti_persone}), "
                   f"{totale:,.0f} $ (+{punti_dollari:.0f})"
                   + (", compra il CEO (+15)" if c_ceo else "")
                   + (", compra il CFO (+10)" if c_cfo else "")
                   + (f", tutto in {giorni} giorni (+5)" if punti_tempo else "")),
    })
    return c


# ======================  4. SALVARE  =========================

def salva(cluster):
    with open(FILE_CLUSTER, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["punteggio", "ticker", "azienda", "n_persone", "totale_dollari",
                    "compra_ceo", "compra_cfo", "primo_acquisto", "ultimo_acquisto",
                    "perche", "chi_ha_comprato"])
        for c in cluster:
            chi = "; ".join(f"{n} ({p['ruolo']}) {p['valore']:,.0f}$"
                            for n, p in sorted(c["persone"].items(), key=lambda x: -x[1]["valore"]))
            w.writerow([c["punteggio"], c["ticker"], c["azienda"], c["n_persone"],
                        round(c["totale"]), "si" if c["ceo"] else "no", "si" if c["cfo"] else "no",
                        c["prima"], c["ultima"], c["perche"], chi])


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    righe = leggi_acquisti()
    if not righe:
        return

    pulite, tolte = pulisci(righe)
    print(f"Acquisti in memoria: {len(righe)}")
    print(f"  tolti perche' piu' vecchi di {FINESTRA_CLUSTER} giorni: {tolte['vecchie']}")
    print(f"  tolti per ticker mancante:            {tolte['ticker']}")
    print(f"  tolti perche' grandi azionisti >10%:  {tolte['azionisti_10']}")
    print(f"  tolti perche' fondi d'investimento:   {tolte['fondi']}")
    print(f"  tolti perche' doppioni:               {tolte['doppioni']}")
    print(f"  rimasti da analizzare:                {len(pulite)}")

    cluster = [dai_punteggio(c) for c in trova_cluster(pulite)]
    cluster.sort(key=lambda c: (c["punteggio"], c["totale"]), reverse=True)
    salva(cluster)

    print("\n" + "=" * 72)
    print(f"🏆 CLASSIFICA CLUSTER (i primi {QUANTI_MOSTRARE} su {len(cluster)})")
    print("=" * 72)
    for pos, c in enumerate(cluster[:QUANTI_MOSTRARE], start=1):
        print(f"\n#{pos}  [{c['punteggio']:>3} punti]  {c['ticker']}  {c['azienda']}")
        print(f"      perche': {c['perche']}")
        for n, p in sorted(c["persone"].items(), key=lambda x: -x[1]["valore"]):
            print(f"        - {n[:30]:<30} ({p['ruolo'][:25]:<25}) {p['valore']:>12,.0f} $")

    print(f"\nClassifica completa salvata in {FILE_CLUSTER} (aprila con Numbers o Excel).")
    print("Ricorda: sono spunti da approfondire, non consigli d'investimento.")


if __name__ == "__main__":
    main()
