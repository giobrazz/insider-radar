# ============================================================
#  INSIDER RADAR - PASSO 2
#  Come il passo 1, ma ora apre OGNI dichiarazione e legge:
#   - chi e' la persona (CEO, direttore, ...)
#   - il codice dell'operazione (P = acquisto, S = vendita, ...)
#   - quante azioni, a che prezzo, per quanti dollari
# ============================================================

import re
import time
import urllib.request
import xml.etree.ElementTree as ET

import os


def leggi_segreto(nome):
    """Legge un dato privato dai Secrets di GitHub o dal file locale segreti.txt."""
    if os.environ.get(nome):
        return os.environ[nome].strip()
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "segreti.txt")
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8") as f:
            for riga in f:
                if riga.strip().startswith(nome + "="):
                    return riga.split("=", 1)[1].strip().strip('"')
    return ""


# 1) LA TUA EMAIL (stessa del passo 1)
CHI_SONO = leggi_segreto("SEC_USER_AGENT") or "Mario Rossi mario.rossi@email.com"

# 2) QUANTE DICHIARAZIONI GUARDARE (massimo 100)
QUANTE = 100

# 3) MOSTRARE SOLO GLI ACQUISTI "P"?  True = si', False = mostra tutto
SOLO_ACQUISTI = False

INDIRIZZO = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    f"?action=getcurrent&type=4&owner=include&count={QUANTE}&output=atom"
)

SIGNIFICATO = {
    "P": "ACQUISTO",
    "S": "vendita",
    "A": "bonus/regalo",
    "M": "opzioni",
    "F": "tasse",
    "G": "donazione",
}


def scarica(url):
    richiesta = urllib.request.Request(url, headers={"User-Agent": CHI_SONO})
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        dati = risposta.read()
    time.sleep(0.15)  # pausa: la SEC vuole al massimo 10 richieste al secondo
    return dati


def elenco_cartelle():
    """Prende l'elenco degli ultimi Form 4 e restituisce i link alle pagine
    delle dichiarazioni (una per dichiarazione, senza doppioni AZIENDA/PERSONA)."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    radice = ET.fromstring(scarica(INDIRIZZO))
    pagine = []
    visti = set()
    for voce in radice.findall("a:entry", ns):
        # teniamo solo i veri Form 4 (e le loro correzioni "4/A"),
        # scartando i moduli che iniziano per 4 ma sono altro (es. 424B2)
        categoria = voce.find("a:category", ns)
        tipo = categoria.get("term", "") if categoria is not None else ""
        if tipo not in ("4", "4/A"):
            continue
        link = voce.find("a:link", ns)
        if link is None:
            continue
        url = link.get("href")
        numero_pratica = url.rsplit("/", 1)[-1].replace("-index.htm", "")
        if numero_pratica not in visti:
            visti.add(numero_pratica)
            pagine.append(url)
    return pagine


def scarica_xml_dichiarazione(url_pagina):
    """Apre la pagina della dichiarazione (quella del link del passo 1)
    e ne ricava il testo XML con i dati veri."""
    # PIANO A: nella pagina cerchiamo il link al file .xml "grezzo"
    # (saltiamo quello dentro la cartella xsl..., che e' la versione grafica)
    pagina = scarica(url_pagina).decode("utf-8", errors="ignore")
    for link in re.findall(r'href="([^"]+\.xml)"', pagina, flags=re.IGNORECASE):
        if "xsl" in link.lower():
            continue
        if link.startswith("/"):
            link = "https://www.sec.gov" + link
        try:
            return scarica(link)
        except Exception:
            break  # se il link non funziona, passiamo al piano B

    # PIANO B: scarichiamo il file .txt completo e ritagliamo il pezzo XML
    url_txt = url_pagina.replace("-index.htm", ".txt")
    tutto = scarica(url_txt).decode("utf-8", errors="ignore")
    inizio = tutto.find("<ownershipDocument")
    fine = tutto.find("</ownershipDocument>")
    if inizio != -1 and fine != -1:
        return tutto[inizio:fine + len("</ownershipDocument>")].encode("utf-8")
    return None


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


def leggi_dichiarazione(testo_xml):
    doc = ET.fromstring(testo_xml)

    azienda = testo(doc, "issuer/issuerName")
    ticker = testo(doc, "issuer/issuerTradingSymbol")
    persona = testo(doc, "reportingOwner/reportingOwnerId/rptOwnerName")

    ruolo = testo(doc, "reportingOwner/reportingOwnerRelationship/officerTitle")
    if not ruolo:
        if testo(doc, "reportingOwner/reportingOwnerRelationship/isDirector") in ("1", "true"):
            ruolo = "Director"
        elif testo(doc, "reportingOwner/reportingOwnerRelationship/isTenPercentOwner") in ("1", "true"):
            ruolo = "Azionista >10%"
        else:
            ruolo = "-"

    operazioni = []
    for op in doc.findall("nonDerivativeTable/nonDerivativeTransaction"):
        codice = testo(op, "transactionCoding/transactionCode")
        azioni = numero(op, "transactionAmounts/transactionShares/value")
        prezzo = numero(op, "transactionAmounts/transactionPricePerShare/value")
        data = testo(op, "transactionDate/value")
        operazioni.append({
            "codice": codice,
            "azioni": azioni,
            "prezzo": prezzo,
            "valore": azioni * prezzo,
            "data": data,
        })

    return azienda, ticker, persona, ruolo, operazioni


def main():
    print("Mi collego alla SEC...")
    cartelle = elenco_cartelle()
    print(f"Trovate {len(cartelle)} dichiarazioni. Le apro una per una (ci vuole un minuto)...\n")

    acquisti_trovati = 0
    for pagina in cartelle:
        try:
            testo_xml = scarica_xml_dichiarazione(pagina)
            if not testo_xml:
                print(f"  (non trovo i dati in: {pagina})")
                continue
            azienda, ticker, persona, ruolo, operazioni = leggi_dichiarazione(testo_xml)
        except Exception as errore:
            print(f"  (salto: {errore} -> {pagina})")
            continue

        for op in operazioni:
            if SOLO_ACQUISTI and op["codice"] != "P":
                continue
            etichetta = SIGNIFICATO.get(op["codice"], "altro")
            segno = ">>>" if op["codice"] == "P" else "   "
            if op["codice"] == "P":
                acquisti_trovati += 1
            print(
                f"{segno} [{op['codice']}] {etichetta:<13} {ticker:<6} {azienda[:28]:<28} "
                f"| {persona[:24]:<24} ({ruolo[:20]}) "
                f"| {op['azioni']:>10,.0f} az. x {op['prezzo']:>8,.2f} $ = {op['valore']:>13,.0f} $"
            )

    print(f"\nFatto! Acquisti veri (codice P) trovati: {acquisti_trovati}")


if __name__ == "__main__":
    main()
