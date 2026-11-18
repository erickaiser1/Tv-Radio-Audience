from datetime import datetime, timedelta
import json
import urllib.request
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

# Configuração da página em modo Widescreen
st.set_page_config(
    page_title="Dashboard Geoespacial - Audiência de TV & Rádio", layout="wide"
)

st.title("📻📺 Dashboard Nacional de Mídia: TV & Rádio (Kantar Ibope Standards)")


# 1. Carregamento de Dados com Cache (expira a cada 1h para atualizar as datas)
@st.cache_data(ttl="1h")
def carregar_dados_e_malha():
  url_geojson_br = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
  with urllib.request.urlopen(url_geojson_br) as response:
    geojson_brasil = json.loads(response.read().decode())

  np.random.seed(42)
  estados_br = [
      ("AC", "Acre"),
      ("AL", "Alagoas"),
      ("AP", "Amapá"),
      ("AM", "Amazonas"),
      ("BA", "Bahia"),
      ("CE", "Ceará"),
      ("DF", "Distrito Federal"),
      ("ES", "Espírito Santo"),
      ("GO", "Goiás"),
      ("MA", "Maranhão"),
      ("MT", "Mato Grosso"),
      ("MS", "Mato Grosso do Sul"),
      ("MG", "Minas Gerais"),
      ("PA", "Pará"),
      ("PB", "Paraíba"),
      ("PR", "Paraná"),
      ("PE", "Pernambuco"),
      ("PI", "Piauí"),
      ("RJ", "Rio de Janeiro"),
      ("RN", "Rio Grande do Norte"),
      ("RS", "Rio Grande do Sul"),
      ("RO", "Rondônia"),
      ("RR", "Roraima"),
      ("SC", "Santa Catarina"),
      ("SP", "São Paulo"),
      ("SE", "Sergipe"),
      ("TO", "Tocantins"),
  ]

  tv_config = {
      "Globo": {"base": 14.5, "var": 3.5, "cor_rgb": [2, 132, 199]},
      "Record": {"base": 6.5, "var": 2.8, "cor_rgb": [225, 29, 72]},
      "SBT": {"base": 5.0, "var": 2.2, "cor_rgb": [16, 185, 129]},
      "Band": {"base": 3.8, "var": 1.8, "cor_rgb": [217, 119, 6]},
      "RedeTV!": {"base": 0.9, "var": 0.6, "cor_rgb": [124, 58, 237]},
  }

  radio_config = {
      "Band FM": {"base": 12.0, "var": 2.5, "cor_rgb": [234, 179, 8]},
      "Nativa FM": {"base": 10.5, "var": 2.2, "cor_rgb": [217, 70, 239]},
      "Alpha FM": {"base": 7.2, "var": 1.8, "cor_rgb": [59, 130, 246]},
      "Jovem Pan FM": {"base": 8.5, "var": 2.0, "cor_rgb": [220, 38, 38]},
      "Rádio Bandeirantes": {"base": 5.0, "var": 1.5, "cor_rgb": [15, 23, 42]},
  }

  # Geração dinâmica das 3 últimas datas com base no dia atual
  hoje = datetime.now()
  datas_disponiveis = [
      (hoje - timedelta(days=3)).strftime("%d/%m/%Y"),
      (hoje - timedelta(days=2)).strftime("%d/%m/%Y"),
      (hoje - timedelta(days=1)).strftime("%d/%m/%Y"),
  ]

  faixas_horarias = {
      "Todas as Faixas": 1.0,
      "06h00 - 12h00 (Manhã)": 0.75,
      "12h00 - 18h00 (Tarde)": 0.95,
      "18h00 - 00h00 (Horário Nobre)": 1.45,
      "00h00 - 06h00 (Madrugada)": 0.40,
  }

  registros = []
  for dt in datas_disponiveis:
    for faixa, mult_hora in faixas_horarias.items():
      if faixa == "Todas as Faixas":
        continue
      for uf, nome_estado in estados_br:
        for emissora, cfg in tv_config.items():
          bonus = (
              2.2
              if emissora == "Band" and uf in ["SP", "RS", "PR", "BA", "DF"]
              else 0.0
          )
          val_bruto = (cfg["base"] + bonus) * mult_hora + np.random.normal(0, 0.4)
          pts = round(max(0.2, val_bruto), 1)
          registros.append({
              "midia": "TV",
              "data": dt,
              "faixa_hora": faixa,
              "uf": uf,
              "estado": nome_estado,
              "emissora": emissora,
              "pontos_ibope": pts,
              "share_pct": round(pts * 2.1, 1),
          })

        for emissora, cfg in radio_config.items():
          bonus = (
              2.5
              if emissora in ["Band FM", "Nativa FM"]
              and uf in ["SP", "RJ", "MG"]
              else 0.0
          )
          val_bruto = (cfg["base"] + bonus) * mult_hora + np.random.normal(0, 0.3)
          pts = round(max(0.1, val_bruto), 1)
          registros.append({
              "midia": "Rádio",
              "data": dt,
              "faixa_hora": faixa,
              "uf": uf,
              "estado": nome_estado,
              "emissora": emissora,
              "pontos_ibope": pts,
              "share_pct": round(pts * 1.8, 1),
          })

  return (
      geojson_brasil,
      pd.DataFrame(registros),
      tv_config,
      radio_config,
      datas_disponiveis,
      list(faixas_horarias.keys()),
      [uf for uf, _ in estados_br],
  )


(
    geojson_brasil,
    df_ibope,
    tv_config,
    radio_config,
    datas_disponiveis,
    faixas_list,
    lista_ufs,
) = carregar_dados_e_malha()

# 2. Painel de Controle Lateral (Sidebar)
st.sidebar.header("🎛️ Filtros do Painel")

tipo_midia = st.sidebar.radio("Selecione a Mídia:", ["TV", "Rádio"])

emissoras_config = tv_config if tipo_midia == "TV" else radio_config
default_emissoras = (
    ["SBT", "Band"] if tipo_midia == "TV" else ["Band FM", "Nativa FM"]
)

emissoras_selecionadas = st.sidebar.multiselect(
    f"Veículos ({tipo_midia}):",
    list(emissoras_config.keys()),
    default=default_emissoras,
)

estados_selecionados = st.sidebar.multiselect(
    "Estados (UFs):", lista_ufs, default=lista_ufs
)

dd_ordenacao = st.sidebar.selectbox(
    "Classificar Ranking:",
    ["Maior Audiência (Desc)", "Menor Audiência (Asc)", "Estado (A-Z)"],
)

dd_data = st.sidebar.selectbox(
    "Data:", ["Todas as Datas"] + datas_disponiveis
)

dd_hora = st.sidebar.selectbox(
    "Faixa Horária:", faixas_list, index=3
)

st.sidebar.markdown("---")
st.sidebar.caption("🔄 *Atualização automática a cada 1 hora.*")


# 3. Bloco com atualização automática a cada 1 hora (@st.fragment)[cite: 1]
@st.fragment(run_every="1h")
def renderizar_conteudo_dinamico():
  local_emissoras = (
      emissoras_selecionadas
      if emissoras_selecionadas
      else list(emissoras_config.keys())
  )
  local_estados = estados_selecionados if estados_selecionados else lista_ufs

  df_f = df_ibope[
      (df_ibope["midia"] == tipo_midia)
      & (df_ibope["emissora"].isin(local_emissoras))
      & (df_ibope["uf"].isin(local_estados))
  ].copy()

  if dd_data != "Todas as Datas":
    df_f = df_f[df_f["data"] == dd_data]
  if dd_hora != "Todas as Faixas":
    df_f = df_f[df_f["faixa_hora"] == dd_hora]

  df_agg = df_f.groupby(["uf", "estado", "emissora"], as_index=False).agg({
      "pontos_ibope": "mean",
      "share_pct": "mean",
  })
  df_agg["pontos_ibope"] = df_agg["pontos_ibope"].round(1)
  df_agg["share_pct"] = df_agg["share_pct"].round(1)

  geojson_dinamico = json.loads(json.dumps(geojson_brasil))
  modo_comparacao = len(local_emissoras) > 1

  geojson_dinamico["features"] = [
      f
      for f in geojson_dinamico["features"]
      if f["properties"]["sigla"] in local_estados
  ]

  if modo_comparacao:
    is_ascending = True if dd_ordenacao == "Menor Audiência (Asc)" else False
    titulo_prefixo = (
        "MENOR AUDIÊNCIA: " if is_ascending else "MAIOR AUDIÊNCIA: "
    )

    df_lideres = df_agg.sort_values(
        "pontos_ibope", ascending=is_ascending
    ).drop_duplicates("uf")
    df_mapa = df_lideres.set_index("uf")

    for feature in geojson_dinamico["features"]:
      uf = feature["properties"]["sigla"]
      if uf in df_mapa.index:
        lider = df_mapa.loc[uf, "emissora"]
        pts = float(df_mapa.loc[uf, "pontos_ibope"])
        shr = float(df_mapa.loc[uf, "share_pct"])
        r, g, b = emissoras_config[lider]["cor_rgb"]

        feature["properties"]["titulo_destaque"] = (
            f"{titulo_prefixo}{lider}"
        )
        feature["properties"]["veiculo_destaque"] = lider
        feature["properties"]["pontos_ibope"] = f"{pts:.1f} pts"
        feature["properties"]["share_pct"] = f"{shr:.1f}%"
        feature["properties"]["fill_color"] = [r, g, b, 205]
      else:
        feature["properties"]["titulo_destaque"] = "Sem dados no período"
        feature["properties"]["veiculo_destaque"] = "-"
        feature["properties"]["pontos_ibope"] = "0.0 pts"
        feature["properties"]["share_pct"] = "0.0%"
        feature["properties"]["fill_color"] = [203, 213, 225, 80]

    itens_legenda = "".join([
        f"<span style='display:inline-flex; align-items:center; gap:5px;"
        f" font-size:12px; font-weight:800;'><span style='width:12px;"
        f" height:12px; border-radius:3px;"
        f" background:rgb({emissoras_config[em]['cor_rgb'][0]},{emissoras_config[em]['cor_rgb'][1]},{emissoras_config[em]['cor_rgb'][2]});"
        f" display:inline-block;'></span>{em}</span>"
        for em in local_emissoras
    ])
    bloco_legenda = (
        f"<div style='display:flex; gap:14px; flex-wrap:wrap;'>"
        f"{itens_legenda}</div>"
    )
  else:
    emissora_unica = local_emissoras[0]
    df_mapa = df_agg[df_agg["emissora"] == emissora_unica].set_index("uf")
    max_pts = df_mapa["pontos_ibope"].max() if not df_mapa.empty else 1.0
    min_pts = df_mapa["pontos_ibope"].min() if not df_mapa.empty else 0.0
    r_base, g_base, b_base = emissoras_config[emissora_unica]["cor_rgb"]

    for feature in geojson_dinamico["features"]:
      uf = feature["properties"]["sigla"]
      if uf in df_mapa.index:
        pts = float(df_mapa.loc[uf, "pontos_ibope"])
        shr = float(df_mapa.loc[uf, "share_pct"])
        norm = (pts - min_pts) / max((max_pts - min_pts), 0.1)
        alpha = int(65 + (norm * 175))

        feature["properties"]["titulo_destaque"] = (
            f"VEÍCULO: {emissora_unica}"
        )
        feature["properties"]["veiculo_destaque"] = emissora_unica
        feature["properties"]["pontos_ibope"] = f"{pts:.1f} pts"
        feature["properties"]["share_pct"] = f"{shr:.1f}%"
        feature["properties"]["fill_color"] = [r_base, g_base, b_base, alpha]
      else:
        feature["properties"]["titulo_destaque"] = "Sem dados"
        feature["properties"]["veiculo_destaque"] = "-"
        feature["properties"]["pontos_ibope"] = "0.0 pts"
        feature["properties"]["share_pct"] = "0.0%"
        feature["properties"]["fill_color"] = [203, 213, 225, 80]

    bloco_legenda = (
        f"<div style='display:flex; align-items:center; gap:8px;'><span"
        f" style='font-size:11px; color:#64748B;'>Mín: {min_pts:.1f}"
        f" pts</span><div style='width:140px; height:11px; border-radius:5px;"
        f" background:linear-gradient(90deg,"
        f" rgba({r_base},{g_base},{b_base},0.25) 0%,"
        f" rgba({r_base},{g_base},{b_base},0.95)"
        f" 100%);'></div><span style='font-size:11px; font-weight:800;'>Máx:"
        f" {max_pts:.1f} pts</span></div>"
    )

  if modo_comparacao:
    df_rank = df_agg.copy()
  else:
    df_rank = df_mapa.reset_index().copy()

  if not df_rank.empty:
    if dd_ordenacao == "Maior Audiência (Desc)":
      df_rank = df_rank.sort_values("pontos_ibope", ascending=False)
    elif dd_ordenacao == "Menor Audiência (Asc)":
      df_rank = df_rank.sort_values("pontos_ibope", ascending=True)
    else:
      df_rank = df_rank.sort_values("estado", ascending=True)

    top5_items = " &nbsp;|&nbsp; ".join([
        f"<b>#{i+1} {r['uf']}</b>: {r['pontos_ibope']:.1f} pts ({r['emissora']})"
        for i, (_, r) in enumerate(df_rank.head(5).iterrows())
    ])
  else:
    top5_items = "Nenhum dado encontrado para os filtros selecionados."

  # 4. Renderização HTML e Mapa PyDeck na Tela Principal
  st.markdown(
      f"""
    <div style='font-family: Segoe UI, sans-serif; background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px 18px; margin-bottom: 12px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 1px solid #E2E8F0; padding-bottom: 8px; margin-bottom: 8px;'>
            <span style='font-size: 11px; font-weight: 800; color: #334155; text-transform: uppercase;'>Comparativo Ativo ({tipo_midia}):</span>
            {bloco_legenda}
        </div>
        <div style='font-size: 12px; color: #0F172A;'>
            <span style='font-size: 11px; font-weight: 800; color: #0284C7; text-transform: uppercase;'>Ranking ({dd_ordenacao.split(' ')[0]}): </span>
            {top5_items}
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  camada_estados = pdk.Layer(
      "GeoJsonLayer",
      data=geojson_dinamico,
      stroked=True,
      filled=True,
      extruded=False,
      get_fill_color="properties.fill_color",
      get_line_color=[15, 23, 42, 160],
      link_width_min_pixels=1.2,
      pickable=True,
      auto_highlight=True,
      highlight_color=[250, 204, 21, 140],
  )

  view_state = pdk.ViewState(
      latitude=-14.2350, longitude=-51.9253, zoom=3.4, pitch=0, bearing=0
  )

  tooltip = {
      "html": """
            <div style='font-family: Segoe UI, sans-serif; padding: 8px; min-width: 200px;'>
                <div style='font-size: 10px; color: #64748B; text-transform: uppercase; font-weight: bold;'>Estado ({sigla})</div>
                <div style='font-size: 14px; font-weight: 800; color: #0284C7;'>{name}</div>
                <div style='font-size: 11px; font-weight: 800; color: #334155; margin-bottom: 6px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px;'>{titulo_destaque}</div>
                <div style='font-size: 12px; margin-top: 4px;'>Veículo: <b>{veiculo_destaque}</b></div>
                <div style='font-size: 12px;'>Audiência: <b>{pontos_ibope}</b></div>
                <div style='font-size: 12px;'>Share: <b>{share_pct}</b></div>
            </div>
        """,
      "style": {
          "backgroundColor": "#FFFFFF",
          "border": "1px solid #CBD5E1",
          "borderRadius": "8px",
          "boxShadow": "0 4px 10px rgba(0, 0, 0, 0.12)",
      },
  }

  deck = pdk.Deck(
      layers=[camada_estados],
      initial_view_state=view_state,
      tooltip=tooltip,
      map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  )

  st.pydeck_chart(deck, use_container_width=True)


# Executa o bloco que se atualiza sozinho a cada hora
renderizar_conteudo_dinamico()
