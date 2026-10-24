import flet as ft
import flet.canvas as cv
import pandas as pd
from datetime import datetime
from motor_datos import cargar_y_calcular_portafolio
import os

def fmt_eur(valor):
    """Formatea al estilo europeo: € 15.218,12"""
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def fmt_ars(valor):
    """Formatea pesos argentinos sin decimales: $ 22.971.000 ARS"""
    s = f"{valor:,.0f}".replace(",", ".")
    return f"$ {s} ARS"

def fmt_shares(valor):
    """Formatea cantidad de acciones/cuotapartes quitando ceros innecesarios"""
    if abs(valor - round(valor)) < 0.001:
        return f"{int(round(valor))}"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def main(page: ft.Page):
    page.title = "Mi Portfolio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0D1117"
    page.padding = 18
    page.window.width = 440
    page.window.height = 900
    page.scroll = ft.ScrollMode.ADAPTIVE

    lbl_estado = ft.Text("Actualizando cotizaciones...", size=12, color="#8B949E")
    contenedor_tarjetas = ft.Column(spacing=14)

    # Estado interactivo del gráfico
    estado_grafico = {
        "region": "GLOBAL",   # GLOBAL | EUR | ARG
        "metrica": "valor",   # valor | ganancia | pct
        "rango": "1A",        # 1M | 6M | 1A | TODO
        "series": None
    }

    def crear_barra_global(res_pais):
        inv_total = float(res_pais["Invertido_EUR"].sum())
        val_total = float(res_pais["Valor_Actual_EUR"].sum())
        gan_total = val_total - inv_total
        pct_total = (gan_total / inv_total * 100) if inv_total > 0 else 0.0

        es_pos = gan_total >= 0
        col_pl = "#00E676" if es_pos else "#FF5252"
        signo = "+" if es_pos else ""

        return ft.Container(
            bgcolor="#161F30",
            border_radius=16,
            padding=ft.padding.symmetric(horizontal=18, vertical=14),
            border=ft.border.all(1, "#263859"),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("PATRIMONIO TOTAL GLOBAL", size=11, weight=ft.FontWeight.BOLD, color="#79C0FF"),
                            ft.Text(fmt_eur(val_total), size=26, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            ft.Text(f"Invertido: {fmt_eur(inv_total)}", size=11, color="#8B949E"),
                        ],
                    ),
                    ft.Container(
                        bgcolor="#112A22" if es_pos else "#2C1518",
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        content=ft.Column(
                            spacing=1,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Text(f"{signo}{fmt_eur(gan_total)}", size=13, weight=ft.FontWeight.BOLD, color=col_pl),
                                ft.Text(f"{signo}{pct_total:.2f}%", size=12, weight=ft.FontWeight.W_600, color=col_pl),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def crear_item_broker_desplegable(broker_nombre, row_b, df_activos_broker):
        val_b = float(row_b["Valor_Actual_EUR"])
        gan_b = float(row_b["Ganancia_EUR"])
        pct_b = float(row_b["Rendimiento_%"]) if row_b["Invertido_EUR"] > 0 else 0.0
        s_b = "+" if gan_b >= 0 else ""
        col_b = "#00E676" if gan_b >= 0 else "#FF5252"

        filas_activos = []
        if df_activos_broker is not None and not df_activos_broker.empty:
            for (ticker, tipo), row_a in df_activos_broker.iterrows():
                shares = float(row_a["Net_Shares"])
                val_a = float(row_a["Valor_Actual_EUR"])
                gan_a = float(row_a["Ganancia_EUR"])
                pct_a = float(row_a["Rendimiento_%"]) if row_a["Invertido_EUR"] > 0 else 0.0
                s_a = "+" if gan_a >= 0 else ""
                col_a = "#00E676" if gan_a >= 0 else "#FF5252"

                filas_activos.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#21262D")),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
                                            controls=[
                                                ft.Text(ticker, size=12, weight=ft.FontWeight.BOLD, color="#E6EDF3"),
                                                ft.Text(tipo, size=10, color="#8B949E"),
                                            ],
                                        ),
                                        ft.Text(f"{fmt_shares(shares)} nominales", size=11, color="#8B949E"),
                                    ],
                                ),
                                ft.Column(
                                    spacing=1,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text(fmt_eur(val_a), size=12, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                                        ft.Text(f"{s_a}{fmt_eur(gan_a)} ({s_a}{pct_a:.1f}%)", size=11, color=col_a),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        panel_activos = ft.Container(
            visible=False,
            bgcolor="#0D1117",
            border_radius=8,
            margin=ft.margin.only(top=4),
            padding=ft.padding.symmetric(vertical=4, horizontal=4),
            content=ft.Column(spacing=2, controls=filas_activos),
        )

        icono_flecha = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=18, color="#8B949E")

        def toggle_broker(e):
            panel_activos.visible = not panel_activos.visible
            icono_flecha.icon = (
                ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if panel_activos.visible else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            )
            page.update()

        cabecera_broker = ft.Container(
            bgcolor="#161B22",
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=9),
            on_click=toggle_broker,
            ink=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            icono_flecha,
                            ft.Text(broker_nombre, size=13, color="#C9D1D9", weight=ft.FontWeight.W_500),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text(fmt_eur(val_b), size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            ft.Text(f"({s_b}{pct_b:.1f}%)", size=12, color=col_b),
                        ],
                    ),
                ],
            ),
        )

        return ft.Column(spacing=0, controls=[cabecera_broker, panel_activos])

    def crear_tarjeta_region(titulo, codigo_badge, color_badge, datos_pais, df_brokers, df_activos_pais, fx, es_argentina=False):
        invertido = float(datos_pais["Invertido_EUR"])
        actual = float(datos_pais["Valor_Actual_EUR"])
        ganancia = float(datos_pais["Ganancia_EUR"])
        rend_pct = float(datos_pais["Rendimiento_%"]) if invertido > 0 else 0.0

        es_positivo = ganancia >= 0
        color_pl = "#00E676" if es_positivo else "#FF5252"
        bg_badge = "#112A22" if es_positivo else "#2C1518"
        signo = "+" if es_positivo else ""

        controles_valor = [
            ft.Text(fmt_eur(actual), size=30, weight=ft.FontWeight.BOLD, color="#FFFFFF")
        ]
        if es_argentina:
            actual_ars = actual * fx["EUR_ARS_HOY"]
            controles_valor.append(
                ft.Text(fmt_ars(actual_ars), size=13, color="#8B949E", weight=ft.FontWeight.W_500)
            )

        filas_brokers = []
        for broker_nombre, row_b in df_brokers.iterrows():
            sub_activos = None
            if df_activos_pais is not None and broker_nombre in df_activos_pais.index.get_level_values(0):
                sub_activos = df_activos_pais.loc[broker_nombre]
            filas_brokers.append(crear_item_broker_desplegable(broker_nombre, row_b, sub_activos))

        return ft.Container(
            bgcolor="#1E242C",
            border_radius=18,
            padding=18,
            border=ft.border.all(1, "#30363D"),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Container(
                                        bgcolor=color_badge,
                                        border_radius=6,
                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                        content=ft.Text(codigo_badge, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    ),
                                    ft.Text(titulo, size=16, weight=ft.FontWeight.W_600, color="#E6EDF3"),
                                ],
                            ),
                            ft.Text(f"Inv: {fmt_eur(invertido)}", size=12, color="#8B949E"),
                        ],
                    ),
                    ft.Column(spacing=2, controls=controles_valor),
                    ft.Container(
                        bgcolor=bg_badge,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        content=ft.Text(
                            f"{signo}{fmt_eur(ganancia)}  ({signo}{rend_pct:.2f}%)",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=color_pl,
                        ),
                    ),
                    ft.Divider(height=6, color="#30363D"),
                    ft.Column(spacing=6, controls=filas_brokers),
                ],
            ),
        )

    def crear_tarjeta_grafico():
        """Crea la tarjeta del gráfico cronológico interactivo usando Canvas vectorial."""
        lbl_max = ft.Text("", size=11, color="#8B949E")
        lbl_min = ft.Text("", size=11, color="#8B949E")
        lbl_f_ini = ft.Text("", size=11, color="#8B949E")
        lbl_f_fin = ft.Text("", size=11, color="#8B949E")
        lbl_resumen_curva = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color="#FFFFFF")

        ancho_cv = 340
        alto_cv = 170
        lienzo = cv.Canvas(width=ancho_cv, height=alto_cv)

        fila_botones_region = ft.Row(spacing=6)
        fila_botones_metrica = ft.Row(spacing=6)
        fila_botones_rango = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.END)

        def fmt_metrica(val, metrica):
            if metrica == "pct":
                s = "+" if val >= 0 else ""
                return f"{s}{val:.1f}%"
            return fmt_eur(val)

        def redibujar_grafico():
            series = estado_grafico["series"]
            if not series:
                return

            reg = estado_grafico["region"]
            met = estado_grafico["metrica"]
            rng = estado_grafico["rango"]

            df_s = series[reg].copy()
            # Quitamos las fechas iniciales donde la región aún tenía 0 inversión
            df_s = df_s[df_s["invertido"] > 0].reset_index(drop=True)

            if df_s.empty:
                lienzo.shapes.clear()
                lbl_resumen_curva.value = "Sin datos en este período"
                return

            hoy = df_s["fecha"].max()
            if rng == "1M":
                df_s = df_s[df_s["fecha"] >= (hoy - pd.Timedelta(days=32))]
            elif rng == "6M":
                df_s = df_s[df_s["fecha"] >= (hoy - pd.Timedelta(days=185))]
            elif rng == "1A":
                df_s = df_s[df_s["fecha"] >= (hoy - pd.Timedelta(days=366))]

            if len(df_s) < 2:
                df_s = series[reg].tail(5).reset_index(drop=True)

            valores = df_s[met].tolist()
            fechas = df_s["fecha"].tolist()

            v_min, v_max = min(valores), max(valores)
            v_actual = valores[-1]
            v_inicial = valores[0]

            # Color según la evolución o signo
            es_positivo = (v_actual >= 0) if met in ["ganancia", "pct"] else (v_actual >= v_inicial)
            color_linea = "#00E676" if es_positivo else "#FF5252"
            color_relleno = "#2200E676" if es_positivo else "#22FF5252"

            lbl_resumen_curva.value = fmt_metrica(v_actual, met)
            lbl_resumen_curva.color = color_linea if met in ["ganancia", "pct"] else "#FFFFFF"
            lbl_max.value = f"Máx: {fmt_metrica(v_max, met)}"
            lbl_min.value = f"Mín: {fmt_metrica(v_min, met)}"
            lbl_f_ini.value = fechas[0].strftime("%d/%m/%Y")
            lbl_f_fin.value = fechas[-1].strftime("%d/%m/%Y")

            # Construcción de coordenadas X, Y
            rango_v = (v_max - v_min) if (v_max - v_min) > 1e-6 else 1.0
            pad_y = 14
            h_util = alto_cv - 2 * pad_y
            n = len(valores)

            puntos = []
            for i, val in enumerate(valores):
                x = (i / (n - 1)) * ancho_cv
                y = pad_y + h_util * (1.0 - (val - v_min) / rango_v)
                puntos.append((x, y))

            formas = []
            # 3 líneas guía horizontales punteadas/suaves
            for frac in [0.1, 0.5, 0.9]:
                yg = alto_cv * frac
                formas.append(cv.Line(0, yg, ancho_cv, yg, paint=ft.Paint(color="#21262D", stroke_width=1)))

            # Polígono de área sombreada bajo la curva
            elems_area = [cv.Path.MoveTo(puntos[0][0], alto_cv), cv.Path.LineTo(puntos[0][0], puntos[0][1])]
            for px, py in puntos[1:]:
                elems_area.append(cv.Path.LineTo(px, py))
            elems_area.append(cv.Path.LineTo(puntos[-1][0], alto_cv))
            elems_area.append(cv.Path.Close())
            formas.append(cv.Path(elements=elems_area, paint=ft.Paint(color=color_relleno, style=ft.PaintingStyle.FILL)))

            # Línea principal de la curva
            elems_linea = [cv.Path.MoveTo(puntos[0][0], puntos[0][1])]
            for px, py in puntos[1:]:
                elems_linea.append(cv.Path.LineTo(px, py))
            formas.append(
                cv.Path(
                    elements=elems_linea,
                    paint=ft.Paint(color=color_linea, stroke_width=2.5, style=ft.PaintingStyle.STROKE),
                )
            )

            # Punto brillante al final (valor actual)
            formas.append(cv.Circle(puntos[-1][0], puntos[-1][1], 4, paint=ft.Paint(color=color_linea)))

            lienzo.shapes = formas

        def actualizar_chips():
            # Región
            fila_botones_region.controls.clear()
            for cod, texto in [("GLOBAL", "Global"), ("EUR", "Europa"), ("ARG", "Argentina")]:
                activo = estado_grafico["region"] == cod
                def click_reg(e, c=cod):
                    estado_grafico["region"] = c
                    actualizar_chips()
                    redibujar_grafico()
                    page.update()

                fila_botones_region.controls.append(
                    ft.Container(
                        bgcolor="#1F6FEB" if activo else "#161B22",
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        on_click=click_reg,
                        ink=True,
                        content=ft.Text(texto, size=12, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL, color="#FFFFFF" if activo else "#8B949E"),
                    )
                )

            # Métrica
            fila_botones_metrica.controls.clear()
            for cod, texto in [("valor", "Valor (€)"), ("ganancia", "Ganancia (€)"), ("pct", "Rendimiento (%)")]:
                activo = estado_grafico["metrica"] == cod
                def click_met(e, c=cod):
                    estado_grafico["metrica"] = c
                    actualizar_chips()
                    redibujar_grafico()
                    page.update()

                fila_botones_metrica.controls.append(
                    ft.Container(
                        bgcolor="#238636" if activo else "#161B22",
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        on_click=click_met,
                        ink=True,
                        content=ft.Text(texto, size=11, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL, color="#FFFFFF" if activo else "#8B949E"),
                    )
                )

            # Rango temporal
            fila_botones_rango.controls.clear()
            for cod in ["1M", "6M", "1A", "TODO"]:
                activo = estado_grafico["rango"] == cod
                def click_rng(e, c=cod):
                    estado_grafico["rango"] = c
                    actualizar_chips()
                    redibujar_grafico()
                    page.update()

                fila_botones_rango.controls.append(
                    ft.Container(
                        bgcolor="#30363D" if activo else "transparent",
                        border_radius=6,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        on_click=click_rng,
                        ink=True,
                        content=ft.Text(cod, size=11, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL, color="#58A6FF" if activo else "#8B949E"),
                    )
                )

        actualizar_chips()
        redibujar_grafico()

        return ft.Container(
            bgcolor="#1E242C",
            border_radius=18,
            padding=18,
            border=ft.border.all(1, "#30363D"),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Evolución Histórica", size=16, weight=ft.FontWeight.W_600, color="#E6EDF3"),
                            lbl_resumen_curva,
                        ],
                    ),
                    fila_botones_region,
                    fila_botones_metrica,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[lbl_max, fila_botones_rango],
                    ),
                    ft.Container(
                        bgcolor="#161B22",
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=10, vertical=10),
                        alignment=ft.alignment.CENTER,
                        content=lienzo,
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[lbl_f_ini, lbl_min, lbl_f_fin],
                    ),
                ],
            ),
        )

    def actualizar_datos(e=None):
        btn_refresh.disabled = True
        lbl_estado.value = "Descargando Google Sheet y cotizaciones..."
        page.update()

        try:
            datos = cargar_y_calcular_portafolio()
            fx = datos["fx"]
            res_pais = datos["resumen_pais"]
            res_broker = datos["resumen_broker"]
            res_activo = datos["resumen_activo"]
            estado_grafico["series"] = datos["series_historicas"]

            contenedor_tarjetas.controls.clear()

            # 0. Barra Superior de Patrimonio Total Global
            contenedor_tarjetas.controls.append(crear_barra_global(res_pais))

            # 1. Tarjeta Patrimonio Europa
            if "EUR" in res_pais.index:
                activos_eur = res_activo.loc["EUR"] if "EUR" in res_activo.index.get_level_values(0) else None
                contenedor_tarjetas.controls.append(
                    crear_tarjeta_region(
                        "Patrimonio Europa", "EUR", "#1F6FEB",
                        res_pais.loc["EUR"],
                        res_broker.loc["EUR"],
                        activos_eur,
                        fx, es_argentina=False
                    )
                )

            # 2. Tarjeta Patrimonio Argentina
            if "ARG" in res_pais.index:
                activos_arg = res_activo.loc["ARG"] if "ARG" in res_activo.index.get_level_values(0) else None
                contenedor_tarjetas.controls.append(
                    crear_tarjeta_region(
                        "Patrimonio Argentina", "ARG", "#0088CC",
                        res_pais.loc["ARG"],
                        res_broker.loc["ARG"],
                        activos_arg,
                        fx, es_argentina=True
                    )
                )

            # 3. Tarjeta del Gráfico Cronológico Interactivo
            contenedor_tarjetas.controls.append(crear_tarjeta_grafico())

            # Footer con referencias de cotizaciones del día
            contenedor_tarjetas.controls.append(
                ft.Container(
                    padding=ft.padding.only(top=4),
                    alignment=ft.alignment.CENTER,
                    content=ft.Text(
                        f"EUR/USD: {fx['EUR_USD_HOY']:.4f}  •  MEP: ${fx['USD_ARS_HOY']:,.0f}  •  UVA: ${fx['UVA_HOY']:,.2f}",
                        size=11, color="#8B949E", text_align=ft.TextAlign.CENTER
                    ),
                )
            )

            ahora = datetime.now().strftime("%H:%M:%S")
            lbl_estado.value = f"Actualizado hoy a las {ahora}"
        except Exception as ex:
            lbl_estado.value = f"Error al actualizar: {ex}"

        btn_refresh.disabled = False
        page.update()

    btn_refresh = ft.IconButton(
        icon=ft.Icons.REFRESH_ROUNDED,
        icon_color="#58A6FF",
        tooltip="Actualizar datos",
        on_click=actualizar_datos
    )

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Text("Mis Inversiones", size=24, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    lbl_estado,
                ],
            ),
            btn_refresh,
        ],
    )

    page.add(header, ft.Divider(height=10, color="transparent"), contenedor_tarjetas)
    actualizar_datos()

if __name__ == "__main__":
    ft.app(target=main)