# ============================================================
#  INSIDER RADAR - PASSO 1
#  Scarica dal sito della SEC gli ultimi Form 4 depositati
#  (le dichiarazioni di acquisto/vendita dei dirigenti)
#  e li stampa sullo schermo.
# ============================================================

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


# 1) LA TUA EMAIL
# La SEC chiede a chi usa i suoi dati di presentarsi con nome ed email.
# Ora la legge dal file segreti.txt.
CHI_SONO = leggi_segreto("SEC_USER_AGENT") or "Mario Rossi mario.rossi@email.com"

# 2) L'INDIRIZZO DA CUI PRENDIAMO I DATI
# E' l'elenco "in tempo reale" degli ultimi Form 4 pubblicati.
INDIRIZZO = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=4&owner=include&count=40&output=atom"
)


def scarica_ultimi_form4():
    richiesta = urllib.request.Request(INDIRIZZO, headers={"User-Agent": CHI_SONO})
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        return risposta.read()


def main():
    print("Mi collego alla SEC...\n")
    dati = scarica_ultimi_form4()

    # I dati arrivano in un formato chiamato "Atom" (una specie di elenco notizie)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    radice = ET.fromstring(dati)
    voci = radice.findall("a:entry", ns)

    print(f"Trovate {len(voci)} voci. Ecco le piu' recenti:\n")
    for voce in voci:
        titolo = voce.findtext("a:title", default="", namespaces=ns)
        data = voce.findtext("a:updated", default="", namespaces=ns)[:16].replace("T", " ")
        link = voce.find("a:link", ns)
        url = link.get("href") if link is not None else ""

        # Ogni dichiarazione compare due volte:
        #  (Issuer)    = l'azienda
        #  (Reporting) = la persona che ha comprato/venduto
        if "(Issuer)" in titolo:
            chi = "AZIENDA "
        elif "(Reporting)" in titolo:
            chi = "PERSONA "
        else:
            chi = "        "

        print(f"{data}  {chi}  {titolo}")
        print(f"                    {url}\n")

    print("Fatto! Se vedi l'elenco qui sopra, il collegamento con la SEC funziona.")


if __name__ == "__main__":
    main()
