import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Planificador IPO Maestro", layout="centered", initial_sidebar_state="collapsed")

st.title("📲 Planificador de Tareas e Inspecciones IPO")

# --- BANCO DE DATOS DE TÉCNICOS EN MEMORIA ---
if 'tecnicos_2027' not in st.session_state:
    st.session_state.tecnicos_2027 = {
        'Óscar Iglesias': {'nov_h': 88, 'dic_h': 56, '2027_h': 104},
        'Pablo Babarro': {'nov_h': 48, 'dic_h': 56, '2027_h': 160},
        'Dani Capón': {'nov_h': 80, 'dic_h': 80, '2027_h': 40}
    }

st.markdown("### 📥 1. Sube el listado de Fábrica")
uploaded_file = st.file_uploader("Selecciona el Excel desde tu ordenador o dispositivo", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            
        df.columns = df.columns.str.strip()
        
        # Identificar columnas críticas de forma flexible
        col_estado = [c for c in df.columns if 'Estado' in c and 'Tarea' in c]
        col_horas = [c for c in df.columns if 'Horas' in c and 'Planif' in c]
        col_limite = [c for c in df.columns if 'Limite' in c and 'IPO' in c]
        col_contratacion = [c for c in df.columns if 'Contratacion' in c or 'Expedición' in c]
        col_inicio = [c for c in df.columns if 'Inicio' in c]
        col_clasif = [c for c in df.columns if 'Clasif' in c or 'IPO' in c and len(c)<15]
        col_dir = [c for c in df.columns if 'Dirección' in c or 'Direccion' in c]
        dir_col = col_dir[0] if col_dir else df.columns[0]

        if col_estado:
            df = df[~df[col_estado[0]].isin(['JD', 'EJ'])]
        
        if col_horas:
            df['Horas_Limpias'] = df[col_horas[0]].astype(str).str.replace('"', '').str.replace(',', '.').astype(float)
            df['Horas Real (80%)'] = (df['Horas_Limpias'] * 0.8).round(2)
            df['Días Reales'] = (df['Horas Real (80%)'] / 8.0).round(2)
        else:
            df['Horas Real (80%)'] = 8.0
            df['Días Reales'] = 1.0
            
        if col_limite:
            df['Fecha Limite IPO'] = pd.to_datetime(df[col_limite[0]], errors='coerce', dayfirst=True)
        else:
            df['Fecha Limite IPO'] = pd.NaT
            
        if col_contratacion:
            df['F. Contratacion'] = pd.to_datetime(df[col_contratacion[0]], errors='coerce', dayfirst=True)
        if col_inicio:
            df['Fecha Inicio'] = pd.to_datetime(df[col_inicio[0]], errors='coerce', dayfirst=True)

        if col_clasif:
            df['Clasif_Limpia'] = pd.to_numeric(df[col_clasif[0]], errors='coerce').fillna(6).astype(int)
        else:
            df['Clasif_Limpia'] = 6
            
        df_criticas = df[df['Clasif_Limpia'].isin([3, 4])].sort_values(by=['Clasif_Limpia', 'Fecha Limite IPO'], ascending=[True, True])
        df_secundarias = df[df['Clasif_Limpia'] == 6]
        df_ordenado = pd.concat([df_criticas, df_secundarias]).dropna(subset=[dir_col])
        
        asignaciones = []
        capacidad_dinamica = {t: {'Nov': v['nov_h'], 'Dic': v['dic_h'], '2027': v['2027_h']} for t, v in st.session_state.tecnicos_2027.items()}
        direccion_tecnico_mapping = {}
        
        for idx, row in df_ordenado.iterrows():
            horas_tarea = row['Horas Real (80%)']
            direccion = row[dir_col]
            clase_ipo = row['Clasif_Limpia']
            f_inicio = row.get(col_inicio[0], pd.NaT) if col_inicio else pd.NaT
            ocor = row.get('Observaciones SEP-OLINK', row.get('Tarea', 'S/N'))
            
            # CORRECCIÓN DE SINTAXIS MÓVIL CRÍTICA
            if pd.notna(f_inicio) and hasattr(f_inicio, 'year') and f_inicio.year >= 2027:
                periodo = '2027'
            else:
                periodo = 'Nov' if clase_ipo in [3, 4] else 'Dic'
                
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
                'Prioridad': f"IPO {clase_ipo}" if clase_ipo != 6 else "Ordinaria",
                'Dirección': direccion,
                'Ref / Tarea': ocor,
                'Días': row['Días Reales'],
                'Mes': periodo,
                'Operario': tecnico_elegido
            })
            
        df_final = pd.DataFrame(asignaciones)
        
        t1, t2, t3 = st.tabs(["📋 Cuadrante", "📊 Gráfico", "📉 Saldos Horas"])
        
        with t1:
            def colorear_prioridad(val):
                if val == 'IPO 3': return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
                if val == 'IPO 4': return 'background-color: #fff2cc; color: #b38600; font-weight: bold;'
                return 'background-color: #e2efda; color: #375623;'
            
            st.dataframe(df_final.style.map(colorear_prioridad, subset=['Prioridad']), use_container_width=True, hide_index=True)
            st.download_button("📥 Descargar CSV", data=df_final.to_csv(index=False).encode('utf-8'), file_name='inspecciones_maestro.csv', mime='text/csv', use_container_width=True)
            
        with t2:
            df_grafico = df_final[df_final['Operario'] != 'Sin Asignar']
            if not df_grafico.empty:
                fig = px.pie(df_grafico, names='Operario', values='Días', title='Reparto de Jornadas', hole=0.3)
                fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("Sube un archivo válido para procesar las gráficas.")
            
        with t3:
            for tec, periodos in capacidad_dinamica.items():
                st.info(f"**{tec}**\n* Nov: {periodos['Nov']:.1f}h\n* Dic: {periodos['Dic']:.1f}h\n* Mes 2027: {periodos['2027']:.1f}h")
                
    except Exception as e:
        st.error(f"Error al procesar los datos del archivo: {e}")

# --- SECCIÓN VISIBLE DIRECTAMENTE ABAJO DEL TODO EN MÓVIL Y ORDENADOR ---
st.markdown("---")
st.markdown("### 👥 2. Configurar o Añadir Técnicos al Equipo")

# Lista interactiva de personal en la pantalla principal
for tec, horas in list(st.session_state.tecnicos_2027.items()):
    with st.expander(f"⚙️ Ver/Modificar Saldo de Horas: {tec}", expanded=False):
        horas['nov_h'] = st.number_input(f"Horas Noviembre ({tec}):", min_value=0, value=int(horas['nov_h']))
        horas['dic_h'] = st.number_input(f"Horas Diciembre ({tec}):", min_value=0, value=int(horas['dic_h']))
        horas['2027_h'] = st.number_input(f"Media Mensual 2027 ({tec}):", min_value=0, value=int(horas['2027_h']))
        if st.button(f"❌ Eliminar a {tec} de la empresa", key=f"del_{tec}"):
            del st.session_state.tecnicos_2027[tec]
            st.rerun()

# Formulario directo para dar de alta nuevos técnicos
with st.expander("➕ BOTÓN PARA AÑADIR NUEVO OPERARIO A LA LISTA", expanded=True):
    nuevo_nombre = st.text_input("Escribe el Nombre y Apellidos del nuevo técnico:")
    h_nov = st.number_input("Horas Noviembre 2026:", min_value=0, value=80)
    h_dic = st.number_input("Horas Diciembre 2026:", min_value=0, value=80)
    h_27 = st.number_input("Media Mensual Año 2027 (Horas):", min_value=0, value=120)
    
    if st.button("💾 CONFIRMAR Y GUARDAR EN LA LISTA", use_container_width=True):
        if nuevo_nombre.strip() != "":
            st.session_state.tecnicos_2027[nuevo_nombre.strip()] = {
                'nov_h': h_nov, 'dic_h': h_dic, '2027_h': h_27
            }
            st.success(f"¡{nuevo_nombre} se ha incorporado de forma definitiva al equipo junto a Óscar, Pablo y Dani!")
            st.rerun()
