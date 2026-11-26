# ============================================================
#  INSIDER RADAR - PASSO 5: AVVISO SU TELEGRAM
#
#  Legge la classifica "cluster.csv" creata dal passo 4
#  e ti manda su Telegram i migliori cluster.
#
#  Ordine di ogni giorno:  STEP3.py -> STEP4.py -> STEP5.py
# ============================================================

import csv
import json
import os
import urllib.parse
import urllib.request

# ------------------------------------------------------------
#  LE TUE IMPOSTAZIONI
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


# Token di BotFather e numero della chat: NON si scrivono piu' qui dentro!
# Sul Mac stanno nel file segreti.txt, su GitHub nei Secrets.
TOKEN = leggi_segreto("TELEGRAM_TOKEN") or "INCOLLA_QUI_IL_TOKEN"
CHAT_ID = leggi_segreto("TELEGRAM_CHAT_ID")

QUANTI_INVIARE = 5        # quanti cluster mandare nel messaggio
PUNTEGGIO_MINIMO = 50     # manda solo i cluster con almeno questi punti
# ------------------------------------------------------------

FILE_CLUSTER = "cluster.csv"


def chiama_telegram(metodo, parametri=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{metodo}"
    dati = urllib.parse.urlencode(parametri or {}).encode()
    with urllib.request.urlopen(url, data=dati, timeout=30) as risposta:
        return json.loads(risposta.read())


def trova_chat_id():
    """Guarda gli ultimi messaggi ricevuti dal bot e ne ricava il numero della chat."""
    risposta = chiama_telegram("getUpdates")
    for aggiornamento in reversed(risposta.get("result", [])):
        messaggio = aggiornamento.get("message") or {}
        chat = messaggio.get("chat") or {}
        if "id" in chat:
            return str(chat["id"])
    return None


def leggi_cluster():
    if not os.path.exists(FILE_CLUSTER):
        print(f"Non trovo {FILE_CLUSTER}: lancia prima STEP4.py!")
        return []
    with open(FILE_CLUSTER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scrivi_messaggio(cluster):
    migliori = [c for c in cluster if int(c["punteggio"]) >= PUNTEGGIO_MINIMO][:QUANTI_INVIARE]
    if not migliori:
        return f"📡 Insider Radar: oggi nessun cluster sopra i {PUNTEGGIO_MINIMO} punti."

    righe = [f"📡 INSIDER RADAR - i migliori {len(migliori)} cluster\n"]
    medaglie = ["🥇", "🥈", "🥉"]
    for i, c in enumerate(migliori):
        icona = medaglie[i] if i < 3 else "▪️"
        extra = []
        if c["compra_ceo"] == "si":
            extra.append("CEO")
        if c["compra_cfo"] == "si":
            extra.append("CFO")
        chi_top = " + ".join(extra) if extra else "dirigenti/direttori"
        righe.append(
            f"{icona} {c['ticker']} - {c['azienda']}\n"
            f"   {c['punteggio']} punti | {c['n_persone']} persone | "
            f"{int(c['totale_dollari']):,} $\n"
            f"   compra: {chi_top} | {c['primo_acquisto']} -> {c['ultimo_acquisto']}\n"
        )
    righe.append("Spunti da approfondire, non consigli d'investimento.")
    return "\n".join(righe)[:4000]   # Telegram accetta max ~4000 caratteri


def main():
    global CHAT_ID
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if TOKEN == "INCOLLA_QUI_IL_TOKEN":
        print("Non trovo il TOKEN: scrivilo nel file segreti.txt (sul Mac)")
        print("oppure nei Secrets del repository (su GitHub).")
        return

    if not CHAT_ID:
        CHAT_ID = trova_chat_id()
        if not CHAT_ID:
            print("Non trovo la tua chat. Apri il bot su Telegram, premi AVVIA e")
            print("scrivigli un messaggio qualsiasi (es. 'ciao'). Poi rilancia lo script.")
            return
        print(f"✅ Ho trovato la tua chat! Il tuo CHAT_ID e': {CHAT_ID}")
        print("   Scrivilo in segreti.txt alla riga TELEGRAM_CHAT_ID=...\n")

    cluster = leggi_cluster()
    if not cluster:
        return
    testo = scrivi_messaggio(cluster)
    chiama_telegram("sendMessage", {"chat_id": CHAT_ID, "text": testo})
    print("📨 Messaggio inviato su Telegram! Controlla il telefono.")
    print("\nEcco cosa ho mandato:\n")
    print(testo)


if __name__ == "__main__":
    main()
