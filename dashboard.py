# ============================================================
#  INSIDER RADAR - PASSO 6: LA DASHBOARD
#
#  Legge acquisti.csv (passo 3) e cluster.csv (passo 4)
#  e li mostra in una pagina web interattiva.
#
#  Per aprirla, dal terminale nella cartella del progetto:
#      streamlit run dashboard.py
#  Si apre da sola nel browser. Per chiuderla: Ctrl + C nel terminale.
# ============================================================

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

CARTELLA = os.path.dirname(os.path.abspath(__file__))
FILE_ACQUISTI = os.path.join(CARTELLA, "acquisti.csv")
FILE_CLUSTER = os.path.join(CARTELLA, "cluster.csv")

st.set_page_config(page_title="Insider Radar", page_icon="📡", layout="wide")


# ======================  CARICARE I DATI  ====================

@st.cache_data(ttl=600)
def carica_dati():
    acquisti = pd.read_csv(FILE_ACQUISTI) if os.path.exists(FILE_ACQUISTI) else pd.DataFrame()
    cluster = pd.read_csv(FILE_CLUSTER) if os.path.exists(FILE_CLUSTER) else pd.DataFrame()
    if not acquisti.empty:
        acquisti["data_operazione"] = pd.to_datetime(acquisti["data_operazione"], errors="coerce")
        acquisti["data_deposito"] = pd.to_datetime(acquisti["data_deposito"], errors="coerce")
        acquisti["ticker"] = acquisti["ticker"].astype(str)
    if not cluster.empty:
        cluster["ticker"] = cluster["ticker"].astype(str)
    return acquisti, cluster


@st.cache_data(ttl=3600, show_spinner=False)
def prezzi(ticker, mesi=6):
    """Prezzi di chiusura da Yahoo Finance. Se qualcosa va storto -> tabella vuota."""
    try:
        import yfinance as yf
        storico = yf.Ticker(ticker).history(period=f"{mesi}mo")
        if storico.empty:
            return pd.DataFrame()
        storico = storico.reset_index()[["Date", "Close"]]
        storico["Date"] = pd.to_datetime(storico["Date"]).dt.tz_localize(None)
        return storico
    except Exception:
        return pd.DataFrame()


acquisti, cluster = carica_dati()

st.title("📡 Insider Cluster-Buy Radar")
st.caption("Acquisti sul mercato (codice P) di dirigenti e direttori, dai Form 4 della SEC. "
           "Spunti da approfondire, non consigli d'investimento.")

if acquisti.empty or cluster.empty:
    st.warning("Non trovo acquisti.csv o cluster.csv. Lancia prima STEP3.py e STEP4.py "
               "nella stessa cartella di questa dashboard.")
    st.stop()


# ======================  FILTRI (barra a sinistra)  ==========

st.sidebar.header("🎛️ Filtri")
punti_min = st.sidebar.slider("Punteggio minimo", 0, 100, 40, step=5)
persone_min = st.sidebar.slider("Persone minime nel cluster", 2, 10, 2)
dollari_min = st.sidebar.number_input("Totale minimo ($)", min_value=0, value=0, step=50_000)
solo_ceo = st.sidebar.checkbox("Solo se compra il CEO")
solo_cfo = st.sidebar.checkbox("Solo se compra il CFO")
cerca = st.sidebar.text_input("Cerca ticker o azienda").strip().upper()

filtrati = cluster[
    (cluster["punteggio"] >= punti_min)
    & (cluster["n_persone"] >= persone_min)
    & (cluster["totale_dollari"] >= dollari_min)
]
if solo_ceo:
    filtrati = filtrati[filtrati["compra_ceo"] == "si"]
if solo_cfo:
    filtrati = filtrati[filtrati["compra_cfo"] == "si"]
if cerca:
    filtrati = filtrati[filtrati["ticker"].str.upper().str.contains(cerca, regex=False)
                        | filtrati["azienda"].str.upper().str.contains(cerca, regex=False)]

st.sidebar.markdown("---")
ultimo = acquisti["data_deposito"].max()
st.sidebar.caption(f"Dati aggiornati al: **{ultimo:%d/%m/%Y}**" if pd.notna(ultimo) else "")
st.sidebar.caption(f"Acquisti in memoria: **{len(acquisti):,}**")


# ======================  NUMERI IN ALTO  =====================

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cluster mostrati", f"{len(filtrati)}", f"su {len(cluster)} totali", delta_color="off")
c2.metric("Dollari nei cluster", f"{filtrati['totale_dollari'].sum() / 1e6:,.1f} M$")
c3.metric("Cluster con il CEO", f"{(filtrati['compra_ceo'] == 'si').sum()}")
c4.metric("Miglior punteggio", f"{filtrati['punteggio'].max() if not filtrati.empty else 0}")

scheda1, scheda2, scheda3 = st.tabs(["🏆 Classifica", "🔎 Dettaglio azienda", "📋 Tutti gli acquisti"])


# ======================  SCHEDA 1: CLASSIFICA  ===============

with scheda1:
    if filtrati.empty:
        st.info("Nessun cluster con questi filtri. Prova ad abbassare il punteggio minimo.")
    else:
        top = filtrati.head(15).iloc[::-1]
        grafico = px.bar(
            top, x="punteggio", y="ticker", orientation="h",
            hover_data={"azienda": True, "n_persone": True, "totale_dollari": ":,.0f"},
            labels={"punteggio": "Punteggio", "ticker": ""},
            title="I migliori cluster",
        )
        grafico.update_layout(height=max(300, 32 * len(top)), margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(grafico, width="stretch")

        tabella = filtrati[["punteggio", "ticker", "azienda", "n_persone", "totale_dollari",
                            "compra_ceo", "compra_cfo", "primo_acquisto", "ultimo_acquisto", "perche"]]
        st.dataframe(
            tabella, hide_index=True, width="stretch",
            column_config={
                "punteggio": st.column_config.ProgressColumn("Punti", min_value=0, max_value=100, format="%d"),
                "ticker": "Ticker",
                "azienda": "Azienda",
                "n_persone": "Persone",
                "totale_dollari": st.column_config.NumberColumn("Totale $", format="%,d"),
                "compra_ceo": "CEO",
                "compra_cfo": "CFO",
                "primo_acquisto": "Primo",
                "ultimo_acquisto": "Ultimo",
                "perche": "Perché",
            },
        )


# ======================  SCHEDA 2: DETTAGLIO  ================

with scheda2:
    if filtrati.empty:
        st.info("Nessun cluster da mostrare con questi filtri.")
    else:
        scelta = st.selectbox(
            "Scegli un cluster",
            filtrati["ticker"].tolist(),
            format_func=lambda t: f"{t} — {filtrati.loc[filtrati['ticker'] == t, 'azienda'].iloc[0]}",
        )
        info = filtrati[filtrati["ticker"] == scelta].iloc[0]
        st.subheader(f"{scelta} — {info['azienda']}")
        st.markdown(f"**{info['punteggio']} punti** · {info['perche']}")

        suoi = acquisti[acquisti["ticker"] == scelta].sort_values("data_operazione")

        # --- grafico del prezzo con gli acquisti segnati sopra ---
        storico = prezzi(scelta)
        if storico.empty:
            st.caption("Prezzi non disponibili per questo ticker (Yahoo Finance non risponde o non lo conosce).")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=storico["Date"], y=storico["Close"], mode="lines",
                                     name="Prezzo", line=dict(width=2)))
            fig.add_trace(go.Scatter(
                x=suoi["data_operazione"], y=suoi["prezzo"], mode="markers", name="Acquisti insider",
                marker=dict(size=(suoi["valore"].clip(lower=1) ** 0.5 / 25).clip(8, 40), symbol="triangle-up"),
                text=suoi["persona"] + " (" + suoi["ruolo"].astype(str) + ")<br>"
                     + suoi["valore"].map("{:,.0f} $".format),
                hovertemplate="%{text}<br>%{x|%d/%m/%Y} a %{y:.2f} $<extra></extra>",
            ))
            fig.update_layout(title="Prezzo degli ultimi 6 mesi (▲ = acquisti dei dirigenti)",
                              height=420, margin=dict(l=10, r=10, t=50, b=10),
                              legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, width="stretch")

            # quanto e' cambiato il prezzo da quando hanno comprato?
            if not suoi.empty and suoi["azioni"].sum() > 0:
                prezzo_medio = (suoi["prezzo"] * suoi["azioni"]).sum() / suoi["azioni"].sum()
                ultimo_prezzo = storico["Close"].iloc[-1]
                variazione = (ultimo_prezzo / prezzo_medio - 1) * 100 if prezzo_medio else 0
                a, b, c = st.columns(3)
                a.metric("Prezzo medio pagato dagli insider", f"{prezzo_medio:,.2f} $")
                b.metric("Ultimo prezzo", f"{ultimo_prezzo:,.2f} $")
                c.metric("Variazione da allora", f"{variazione:+.1f} %")

        st.markdown("**Chi ha comprato**")
        st.dataframe(
            suoi[["data_operazione", "persona", "ruolo", "azioni", "prezzo", "valore"]],
            hide_index=True, width="stretch",
            column_config={
                "data_operazione": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "persona": "Persona", "ruolo": "Ruolo",
                "azioni": st.column_config.NumberColumn("Azioni", format="%,d"),
                "prezzo": st.column_config.NumberColumn("Prezzo $", format="%.2f"),
                "valore": st.column_config.NumberColumn("Valore $", format="%,d"),
            },
        )
        st.link_button("Apri le dichiarazioni sulla SEC",
                       f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={scelta}&type=4")


# ======================  SCHEDA 3: TUTTI GLI ACQUISTI  =======

with scheda3:
    st.markdown("Tutti gli acquisti in memoria, anche quelli che non fanno parte di un cluster.")
    col_a, col_b = st.columns(2)
    minimo = col_a.number_input("Valore minimo per acquisto ($)", min_value=0, value=10_000, step=10_000)
    ruolo = col_b.text_input("Filtra per ruolo (es. CEO, Director)").strip().upper()

    tutti = acquisti[acquisti["valore"] >= minimo]
    if ruolo:
        tutti = tutti[tutti["ruolo"].astype(str).str.upper().str.contains(ruolo, regex=False)]

    per_giorno = tutti.groupby(tutti["data_operazione"].dt.date)["valore"].sum().reset_index()
    if not per_giorno.empty:
        fig = px.bar(per_giorno, x="data_operazione", y="valore",
                     labels={"data_operazione": "", "valore": "Dollari comprati"},
                     title="Quanti dollari hanno comprato gli insider, giorno per giorno")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")

    st.dataframe(
        tutti.sort_values("valore", ascending=False)[
            ["data_operazione", "ticker", "azienda", "persona", "ruolo", "azioni", "prezzo", "valore"]],
        hide_index=True, width="stretch",
        column_config={
            "data_operazione": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "valore": st.column_config.NumberColumn("Valore $", format="%,d"),
            "azioni": st.column_config.NumberColumn("Azioni", format="%,d"),
            "prezzo": st.column_config.NumberColumn("Prezzo $", format="%.2f"),
        },
    )
    st.download_button("⬇️ Scarica questa tabella (CSV)", tutti.to_csv(index=False).encode(),
                       "acquisti_filtrati.csv", "text/csv")
