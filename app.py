import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Planificador IPO", layout="centered", initial_sidebar_state="collapsed")

st.title("📲 Planificador de Tareas IPO")
st.markdown("Toca las tres rayas de arriba a la izquierda para cambiar las horas de los técnicos.")

if 'tecnicos_2027' not in st.session_state:
    st.session_state.tecnicos_2027 = {
        'Óscar Iglesias': {'nov_h': 88, 'dic_h': 56, '2027_h': 104},
        'Pablo Babarro': {'nov_h': 48, 'dic_h': 56, '2027_h': 160},
        'Dani Capón': {'nov_h': 80, 'dic_h': 80, '2027_h': 40}
    }

for tec, horas in list(st.session_state.tecnicos_2027.items()):
    with st.sidebar.expander(f"👤 {tec}", expanded=False):
        horas['nov_h'] = st.number_input(f"Nov 2026:", min_value=0, value=int(horas['nov_h']), key=f"n_{tec}")
        horas['dic_h'] = st.number_input(f"Dic 2026:", min_value=0, value=int(horas['dic_h']), key=f"d_{tec}")
        horas['2027_h'] = st.number_input(f"Media 2027:", min_value=0, value=int(horas['2027_h']), key=f"h27_{tec}")

uploaded_file = st.file_uploader("Selecciona el Excel desde tu dispositivo", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = df.columns.str.strip()
        
        if 'Estado Tarea' in df.columns:
            df = df[~df['Estado Tarea'].isin(['JD', 'EJ'])]
        if 'Horas Planif' in df.columns:
            df['Horas Planif'] = df['Horas Planif'].astype(str).str.replace('"', '').str.replace(',', '.').astype(float)
            df['Horas Real (80%)'] = (df['Horas Planif'] * 0.8).round(2)
            df['Días Reales'] = (df['Horas Real (80%)'] / 8.0).round(2)
            
        if 'Fecha Limite IPO' in df.columns:
            df['Fecha Limite IPO'] = pd.to_datetime(df['Fecha Limite IPO'], errors='coerce', dayfirst=True)
        if 'F. Contratacion' in df.columns:
            df['F. Contratacion'] = pd.to_datetime(df['F. Contratacion'], errors='coerce', dayfirst=True)
        if 'Fecha Inicio' in df.columns:
            df['Fecha Inicio'] = pd.to_datetime(df['Fecha Inicio'], errors='coerce', dayfirst=True)

        vacias_mask = df['Clasif. IPO'].isna() if 'Clasif. IPO' in df.columns else pd.Series(True, index=df.index)
        if 'Clasif. IPO' in df.columns:
            df['Clasif. IPO'] = pd.to_numeric(df['Clasif. IPO'], errors='coerce').fillna(6).astype(int)
        else:
            df['Clasif. IPO'] = 6
            
        df_criticas = df[df['Clasif. IPO'].isin([3, 4])].sort_values(by=['Clasif. IPO', 'Fecha Limite IPO'], ascending=[True, True])
        df_secundarias = df[df['Clasif. IPO'] == 6].sort_values(by=['F. Contratacion'], ascending=[True])
        df_ordenado = pd.concat([df_criticas, df_secundarias]).dropna(subset=['Dirección'])
        
        asignaciones = []
        capacidad_dinamica = {t: {'Nov': v['nov_h'], 'Dic': v['dic_h'], '2027': v['2027_h']} for t, v in st.session_state.tecnicos_2027.items()}
        direccion_tecnico_mapping = {}
        
        for idx, row in df_ordenado.iterrows():
            horas_tarea = row['Horas Real (80%)']
            direccion = row['Dirección']
            clase_ipo = row['Clasif. IPO']
            f_inicio = row['Fecha Inicio']
            ocor = row.get('Observaciones SEP-OLINK', row.get('Numero Pedido', 'S/N'))
            
            tipo_etiqueta = "Sin Clasif (IPO 6)" if vacias_mask.loc[idx] else f"IPO {clase_ipo}"
            periodo = '2027' if pd.notna(f_inicio) and f_inicio.year >= 2027 else ('Nov' if clase_ipo in [3, 4] else 'Dic')
                
            if direccion in direccion_tecnico_mapping:
                tecnico_elegido = direccion_tecnico_mapping[direccion]
            else:
                tecnico_elegido = 'Sin Asignar'
                for tec in capacidad_dinamica.keys():
                    if tec == 'Óscar Iglesias' and periodo == 'Nov':
                        continue
                    if capacidad_dinamica[tec][periodo] >= horas_tarea:
                        tecnico_elegido = tec
                        break
                if tecnico_elegido != 'Sin Asignar':
                    direccion_tecnico_mapping[direccion] = tecnico_elegido
                    
            if tecnico_elegido != 'Sin Asignar':
                capacidad_dinamica[tecnico_elegido][periodo] -= horas_tarea
                
            asignaciones.append({
                'Prioridad': tipo_etiqueta,
                'Dirección': direccion,
                'OCOR': ocor,
                'Días': row['Días Reales'],
                'Mes': periodo,
                'Operario': tecnico_elegido
            })
            
        df_final = pd.DataFrame(asignaciones)
        
        t1, t2, t3 = st.tabs(["📋 Cuadrante", "📊 Gráfico", "📉 Saldos"])
        
        with t1:
            def colorear_prioridad(val):
                if val == 'IPO 3': return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
                if val == 'IPO 4': return 'background-color: #fff2cc; color: #b38600; font-weight: bold;'
                if val == 'IPO 6': return 'background-color: #e2efda; color: #375623;'
                if 'Sin Clasif' in str(val): return 'background-color: #dee2e6; color: #495057;'
                return ''
            
            st.dataframe(df_final.style.map(colorear_prioridad, subset=['Prioridad']), use_container_width=True, hide_index=True)
            st.download_button("📥 Descargar CSV", data=df_final.to_csv(index=False).encode('utf-8'), file_name='inspecciones_movil.csv', mime='text/csv', use_container_width=True)
            
        with t2:
            df_grafico = df_final[df_final['Operario'] != 'Sin Asignar']
            fig = px.pie(df_grafico, names='Operario', values='Días', title='Reparto de Jornadas', hole=0.3)
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
            
        with t3:
            for tec, periodos in capacidad_dinamica.items():
                st.info(f"**{tec}**\n* Nov: {periodos['Nov']:.1f}h\n* Dic: {periodos['Dic']:.1f}h\n* Mes 2027: {periodos['2027']:.1f}h")
                
    except Exception as e:
        st.error(f"Error: {e}")
