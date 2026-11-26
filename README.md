# 📡 Insider Cluster-Buy Radar

Un radar che ogni giorno legge le dichiarazioni ufficiali della **SEC** (Form 4) e trova i **cluster buy**: le aziende americane in cui **più dirigenti diversi** (CEO, CFO, direttori…) comprano azioni **con i propri soldi** nello stesso periodo.

I migliori cluster arrivano ogni mattina su **Telegram**, e una **dashboard** permette di analizzarli.

> ⚠️ Progetto a scopo didattico. I segnali sono spunti da approfondire, **non consigli d'investimento**.

---

## Come funziona

| Passo | File | Cosa fa |
|---|---|---|
| 3 | `STEP3.py` | Scarica l'elenco giornaliero dei Form 4 da SEC EDGAR, tiene solo gli **acquisti sul mercato (codice P)** e li salva in `acquisti.csv` |
| 4 | `STEP4.py` | Toglie il rumore (ticker mancanti, doppioni), trova i cluster e dà a ognuno un **punteggio** → `cluster.csv` |
| 5 | `STEP5.py` | Manda su **Telegram** i migliori cluster del giorno |
| 6 | `dashboard.py` | **Dashboard** interattiva (Streamlit) con filtri, classifica e grafici |
| 7 | `.github/workflows/radar.yml` | **Automazione**: GitHub lancia 3 → 4 → 5 ogni mattina e salva la memoria |

`STEP1.py` e `STEP2.py` sono le prime versioni didattiche (collegamento alla SEC e lettura di un Form 4).

### Il punteggio (max ~100)
- **Persone**: 10 punti a persona (max 40)
- **Dollari**: 100k $ = 10, 1M $ = 20, 10M $ = 30
- **Ruoli**: CEO +15, CFO +10
- **Vicinanza**: tutti gli acquisti entro 5 giorni +5

### Perché solo il codice "P"?
Molte azioni i dirigenti le ricevono come bonus (A), le ottengono da opzioni (M) o le cedono per le tasse (F). Solo **P** è un acquisto fatto di tasca propria sul mercato: il segnale più "onesto".

---

## Usarlo sul Mac

1. Compila `segreti.txt` (email per la SEC, token e chat di Telegram). **Questo file non va mai su GitHub.**
2. Nel terminale, dalla cartella del progetto:
   ```
   python3 STEP3.py
   python3 STEP4.py
   python3 STEP5.py
   ```
3. Dashboard:
   ```
   pip install -r requirements.txt
   streamlit run dashboard.py
   ```

## Automazione su GitHub

Nel repository: **Settings → Secrets and variables → Actions → New repository secret**, e crea:

| Nome | Valore |
|---|---|
| `SEC_USER_AGENT` | `Nome Cognome tua@email.com` |
| `TELEGRAM_TOKEN` | il token di BotFather |
| `TELEGRAM_CHAT_ID` | il numero della tua chat |

Il radar parte da solo dal martedì al sabato alle 5:37 UTC. Si può lanciare anche a mano da **Actions → Insider Radar → Run workflow**.

---

## Fonti dei dati
- [SEC EDGAR](https://www.sec.gov/edgar), indici giornalieri e Form 4 (gratuito, pubblico)
- Prezzi nella dashboard: Yahoo Finance tramite la libreria `yfinance`
