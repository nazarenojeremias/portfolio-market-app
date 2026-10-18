import pandas as pd
import yfinance as yf
import requests

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSW9vrwgvksdlLzpqZQAL0sa8mi8ZW-1jRyK5sUaZUgDkjavSsaSXFtZGlcemUZpHorbjdnmO7Klt4T/pub?gid=0&single=true&output=csv"

COLUMNAS_BASE = [
    "Data", "Country", "Exchange", "Broker", "Tipo", "Ticker", "Currency",
    "Shares Buy", "Cost Per Share Buy", "Shares Sell", "Cost Per Share Sell",
    "Maturity", "Tasa_Anual", "Commission"
]

def obtener_datos_mercado_y_fx(fecha_minima="2020-01-01"):
    """Descarga cotizaciones actuales e históricas de FX (EUR/USD, USD/ARS) y UVA."""
    # 1. Histórico EUR/USD desde Yahoo Finance
    hist_eurusd = yf.Ticker("EURUSD=X").history(start=fecha_minima)[["Close"]].reset_index()
    hist_eurusd["Fecha"] = pd.to_datetime(hist_eurusd["Date"]).dt.tz_localize(None).dt.normalize()
    hist_eurusd = hist_eurusd.rename(columns={"Close": "EUR_USD"}).sort_values("Fecha")
    eur_usd_hoy = float(hist_eurusd["EUR_USD"].iloc[-1])

    # 2. Histórico USD/ARS desde ArgentinaDatos + Dólar MEP actual
    try:
        r_hist_ars = requests.get("https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa", timeout=10).json()
        if not r_hist_ars:
            r_hist_ars = requests.get("https://api.argentinadatos.com/v1/cotizaciones/dolares/blue", timeout=10).json()
        df_ars = pd.DataFrame(r_hist_ars)
        df_ars["Fecha"] = pd.to_datetime(df_ars["fecha"]).dt.normalize()
        df_ars["USD_ARS"] = pd.to_numeric(df_ars["venta"], errors="coerce")
        df_ars = df_ars[["Fecha", "USD_ARS"]].dropna().drop_duplicates("Fecha").sort_values("Fecha")
    except Exception:
        df_ars = pd.DataFrame({"Fecha": [pd.Timestamp("2020-01-01")], "USD_ARS": [1500.0]})

    try:
        r_mep = requests.get("https://dolarapi.com/v1/dolares/bolsa", timeout=5).json()
        dolar_mep_hoy = float(r_mep.get("venta", df_ars["USD_ARS"].iloc[-1]))
    except Exception:
        dolar_mep_hoy = float(df_ars["USD_ARS"].iloc[-1])

    # 3. Histórico completo y valor actual de la UVA (BCRA)
    try:
        r_uva = requests.get("https://api.argentinadatos.com/v1/finanzas/indices/uva", timeout=10).json()
        df_uva = pd.DataFrame(r_uva)
        df_uva["Fecha"] = pd.to_datetime(df_uva["fecha"]).dt.normalize()
        df_uva["UVA"] = pd.to_numeric(df_uva["valor"], errors="coerce")
        df_uva = df_uva[["Fecha", "UVA"]].dropna().drop_duplicates("Fecha").sort_values("Fecha")
        valor_uva_hoy = float(df_uva["UVA"].iloc[-1])
    except Exception:
        df_uva = pd.DataFrame({"Fecha": [pd.Timestamp("2020-01-01")], "UVA": [2159.10]})
        valor_uva_hoy = 2159.10

    return {
        "hist_eurusd": hist_eurusd[["Fecha", "EUR_USD"]],
        "hist_usdars": df_ars,
        "hist_uva": df_uva,
        "EUR_USD_HOY": eur_usd_hoy,
        "USD_ARS_HOY": dolar_mep_hoy,
        "EUR_ARS_HOY": dolar_mep_hoy * eur_usd_hoy,
        "UVA_HOY": valor_uva_hoy
    }

def construir_serie_historica(df, fx, tickers_mercado):
    """Reconstruye la evolución temporal del portafolio para el gráfico interactivo."""
    fecha_inicio = df["Data"].min()
    hoy = pd.Timestamp.today().normalize()

    # Grilla de fechas (cada 5 días + hoy) para que sea ultra rápido y suave al graficar
    fechas = pd.date_range(start=fecha_inicio, end=hoy, freq="5D").tolist()
    if not fechas or fechas[-1] != hoy:
        fechas.append(hoy)
    fechas_idx = pd.DatetimeIndex(fechas)

    # Descargar histórico de todos los tickers de mercado de una sola vez
    precios_df = pd.DataFrame(index=fechas_idx)
    if tickers_mercado:
        try:
            raw_yf = yf.download(tickers_mercado, start=fecha_inicio.strftime("%Y-%m-%d"), progress=False)["Close"]
            if isinstance(raw_yf, pd.Series):
                raw_yf = raw_yf.to_frame(name=tickers_mercado[0])
            raw_yf.index = pd.to_datetime(raw_yf.index).tz_localize(None).normalize()
            raw_yf = raw_yf[~raw_yf.index.duplicated(keep="last")]
            precios_df = raw_yf.reindex(raw_yf.index.union(fechas_idx)).sort_index().ffill().bfill().reindex(fechas_idx)
        except Exception as e:
            print(f"   [Aviso] Error descargando histórico masivo: {e}")

    # Agregar UVA, EUR_USD y USD_ARS a la misma grilla de fechas
    uva_s = fx["hist_uva"].set_index("Fecha")["UVA"]
    uva_s = uva_s[~uva_s.index.duplicated(keep="last")]
    precios_df["UVA"] = uva_s.reindex(uva_s.index.union(fechas_idx)).sort_index().ffill().bfill().reindex(fechas_idx)

    eu_s = fx["hist_eurusd"].set_index("Fecha")["EUR_USD"]
    eu_s = eu_s[~eu_s.index.duplicated(keep="last")]
    fx_eurusd = eu_s.reindex(eu_s.index.union(fechas_idx)).sort_index().ffill().bfill().reindex(fechas_idx)

    ar_s = fx["hist_usdars"].set_index("Fecha")["USD_ARS"]
    ar_s = ar_s[~ar_s.index.duplicated(keep="last")]
    fx_usdars = ar_s.reindex(ar_s.index.union(fechas_idx)).sort_index().ffill().bfill().reindex(fechas_idx)
    fx_eurars = fx_eurusd * fx_usdars

    es_pf = df["Tipo"].astype(str).str.upper().str.contains("PLAZO FIJO")
    historial = {"GLOBAL": [], "EUR": [], "ARG": []}

    for f in fechas_idx:
        # Operaciones ocurridas hasta la fecha f
        mask_activo = df["Data"] <= f
        # Plazos fijos vencidos antes de la fecha f dejan de contarse en f
        mask_vencido = es_pf & df["Maturity"].notna() & (df["Maturity"] < f)
        sub = df[mask_activo & (~mask_vencido)]

        if sub.empty:
            for reg in ["GLOBAL", "EUR", "ARG"]:
                historial[reg].append({"fecha": f, "invertido": 0.0, "valor": 0.0, "ganancia": 0.0, "pct": 0.0})
            continue

        dias = (f - sub["Data"]).dt.days.clip(lower=0)
        factor_tasa = 1.0 + (sub["Tasa_Anual"] / 100.0) * (dias / 365.0)
        shares_ef = sub["Shares Buy"] * factor_tasa.where(es_pf.loc[sub.index], 1.0) - sub["Shares Sell"]

        # Precio de cada ticker en la fecha f
        precios_f = sub["Ticker"].map(lambda t: precios_df.at[f, t] if t in precios_df.columns else 0.0).fillna(0.0)
        val_orig = shares_ef * precios_f

        # Convertir a EUR según el tipo de cambio de la fecha f
        eur_usd_f = float(fx_eurusd.loc[f])
        eur_ars_f = float(fx_eurars.loc[f])
        factores_moneda = sub["Currency"].map({"EUR": 1.0, "USD": eur_usd_f, "ARS": eur_ars_f}).fillna(1.0)
        val_eur = val_orig / factores_moneda
        inv_eur = sub["Costo_Compra_EUR"] - sub["Valor_Venta_EUR"]

        for reg in ["GLOBAL", "EUR", "ARG"]:
            if reg == "GLOBAL":
                inv_r = float(inv_eur.sum())
                val_r = float(val_eur.sum())
            else:
                m_reg = sub["Country"] == reg
                inv_r = float(inv_eur[m_reg].sum())
                val_r = float(val_eur[m_reg].sum())

            gan_r = val_r - inv_r
            pct_r = (gan_r / inv_r * 100.0) if inv_r > 0 else 0.0
            historial[reg].append({
                "fecha": f,
                "invertido": inv_r,
                "valor": val_r,
                "ganancia": gan_r,
                "pct": pct_r
            })

    return {k: pd.DataFrame(v) for k, v in historial.items()}

def cargar_y_calcular_portafolio():
    print("1. Leyendo Google Sheet...")
    df_raw = pd.read_csv(CSV_URL)
    
    cols_presentes = [c for c in COLUMNAS_BASE if c in df_raw.columns]
    df = df_raw[cols_presentes].copy()
    if "Maturity" not in df.columns:
        df["Maturity"] = pd.NaT

    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce").dt.normalize()
    df["Maturity"] = pd.to_datetime(df["Maturity"], dayfirst=True, errors="coerce").dt.normalize()
    df = df.dropna(subset=["Data"]).sort_values("Data").reset_index(drop=True)

    cols_num = ["Shares Buy", "Cost Per Share Buy", "Shares Sell", "Cost Per Share Sell", "Tasa_Anual", "Commission"]
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    print("2. Descargando series históricas de tipos de cambio y precios...")
    fecha_min = df["Data"].min().strftime("%Y-%m-%d")
    fx = obtener_datos_mercado_y_fx(fecha_min)
    print(f"   -> Hoy: EUR/USD: {fx['EUR_USD_HOY']:.4f} | Dólar MEP: ${fx['USD_ARS_HOY']:.2f} | Euro MEP: ${fx['EUR_ARS_HOY']:.2f} | UVA: ${fx['UVA_HOY']:.2f}")

    df = pd.merge_asof(df, fx["hist_eurusd"], left_on="Data", right_on="Fecha", direction="backward")
    df = pd.merge_asof(df, fx["hist_usdars"], left_on="Data", right_on="Fecha", direction="backward")
    df["EUR_USD"] = df["EUR_USD"].bfill().fillna(fx["EUR_USD_HOY"])
    df["USD_ARS"] = df["USD_ARS"].bfill().fillna(fx["USD_ARS_HOY"])
    df["EUR_ARS"] = df["EUR_USD"] * df["USD_ARS"]

    def calcular_conversion(row):
        if row["Currency"] == "EUR":
            return 1.0
        elif row["Currency"] == "USD":
            return row["EUR_USD"]
        elif row["Currency"] == "ARS":
            return row["EUR_ARS"]
        return 1.0

    df["Conversion_Motor"] = df.apply(calcular_conversion, axis=1)

    hoy = pd.Timestamp.today().normalize()
    es_pf = df["Tipo"].astype(str).str.upper().str.contains("PLAZO FIJO")
    pf_vencido = es_pf & df["Maturity"].notna() & (df["Maturity"] < hoy)

    dias_corridos = (hoy - df["Data"]).dt.days.clip(lower=0)
    factor_tasa = 1.0 + (df["Tasa_Anual"] / 100.0) * (dias_corridos / 365.0)

    df["Shares_Buy_Efectivas"] = df["Shares Buy"] * factor_tasa.where(es_pf, 1.0)
    df["Net_Shares"] = (df["Shares_Buy_Efectivas"] - df["Shares Sell"]).where(~pf_vencido, 0.0)

    df["Costo_Compra_EUR"] = (df["Shares Buy"] * df["Cost Per Share Buy"]) / df["Conversion_Motor"]
    df["Valor_Venta_EUR"] = (df["Shares Sell"] * df["Cost Per Share Sell"]) / df["Conversion_Motor"]
    df["Invertido_EUR"] = (df["Costo_Compra_EUR"] - df["Valor_Venta_EUR"]).where(~pf_vencido, 0.0)

    tickers_mercado = [t for t in df["Ticker"].unique() if t != "UVA" and pd.notna(t)]
    precios_actuales = {"UVA": fx["UVA_HOY"]}

    for t in tickers_mercado:
        try:
            precio = yf.Ticker(t).fast_info.get("lastPrice")
            if precio is None:
                hist = yf.Ticker(t).history(period="5d")
                precio = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
            precios_actuales[t] = float(precio)
        except Exception:
            precios_actuales[t] = 0.0

    df["Precio_Hoy"] = df["Ticker"].map(precios_actuales)
    df["Valor_Actual_Moneda_Origen"] = df["Net_Shares"] * df["Precio_Hoy"]

    def convertir_actual_a_eur(row):
        val = row["Valor_Actual_Moneda_Origen"]
        if row["Currency"] == "EUR":
            return val
        elif row["Currency"] == "USD":
            return val / fx["EUR_USD_HOY"]
        elif row["Currency"] == "ARS":
            return val / fx["EUR_ARS_HOY"]
        return val

    df["Valor_Actual_EUR"] = df.apply(convertir_actual_a_eur, axis=1)
    df["Valor_Actual_ARS"] = df["Valor_Actual_EUR"] * fx["EUR_ARS_HOY"]

    resumen_pais = df.groupby("Country")[["Invertido_EUR", "Valor_Actual_EUR"]].sum()
    resumen_pais["Ganancia_EUR"] = resumen_pais["Valor_Actual_EUR"] - resumen_pais["Invertido_EUR"]
    resumen_pais["Rendimiento_%"] = (resumen_pais["Ganancia_EUR"] / resumen_pais["Invertido_EUR"].replace(0, pd.NA)) * 100

    resumen_broker = df.groupby(["Country", "Broker"])[["Invertido_EUR", "Valor_Actual_EUR"]].sum()
    resumen_broker["Ganancia_EUR"] = resumen_broker["Valor_Actual_EUR"] - resumen_broker["Invertido_EUR"]
    resumen_broker["Rendimiento_%"] = (resumen_broker["Ganancia_EUR"] / resumen_broker["Invertido_EUR"].replace(0, pd.NA)) * 100

    df_activos = df[df["Net_Shares"] > 0.0001].copy()
    resumen_activo = df_activos.groupby(["Country", "Broker", "Ticker", "Tipo"])[
        ["Net_Shares", "Invertido_EUR", "Valor_Actual_EUR"]
    ].sum()
    resumen_activo["Ganancia_EUR"] = resumen_activo["Valor_Actual_EUR"] - resumen_activo["Invertido_EUR"]
    resumen_activo["Rendimiento_%"] = (
        resumen_activo["Ganancia_EUR"] / resumen_activo["Invertido_EUR"].replace(0, pd.NA)
    ) * 100

    print("3. Construyendo serie histórica para el gráfico...")
    series_historicas = construir_serie_historica(df, fx, tickers_mercado)

    return {
        "fx": fx,
        "resumen_pais": resumen_pais,
        "resumen_broker": resumen_broker,
        "resumen_activo": resumen_activo,
        "series_historicas": series_historicas,
        "df": df
    }

if __name__ == "__main__":
    cargar_y_calcular_portafolio()