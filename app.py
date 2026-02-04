import os
import streamlit as st
import pandas as pd
from src.io_handler import load_employees, load_holidays
from datetime import timedelta, date
from src.solver import RosterSolver
from typing import List
import io
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="Duty Roster Planner", layout="wide", page_icon="🗓️")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ff4b4b; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True) # <--- Changed this line

# --- SESSION STATE INITIALIZATION ---
if 'roster_df' not in st.session_state:
    st.session_state.roster_df = None
if 'summary_df' not in st.session_state:
    st.session_state.summary_df = None
if 'employees' not in st.session_state:
    st.session_state.employees = None
if 'holidays' not in st.session_state:
    st.session_state.holidays = None

# --- UTILS ---
def get_date_list(start_date: date, end_date: date) -> List[date]:
    if start_date > end_date: return []
    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]

# --- SIDEBAR: INPUTS & CONFIG ---
with st.sidebar:
    st.title("⚙️ Roster Config")
    st.info("Upload your database and select dates to begin.")
    
    uploaded_file = st.file_uploader("1. Upload Employee Excel", type=["xlsx"])
    
    if uploaded_file:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATA_FOLDER = os.path.join(BASE_DIR, "data")
        TEMP_FILE_PATH = os.path.join(DATA_FOLDER, "temp_data.xlsx")
        if not os.path.exists(DATA_FOLDER): os.makedirs(DATA_FOLDER)
        
        with open(TEMP_FILE_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.employees = load_employees(TEMP_FILE_PATH)
        st.session_state.holidays = load_holidays(TEMP_FILE_PATH)
        st.success("File Loaded Successfully")

    st.divider()
    
    st.subheader("2. Date Range")
    date_range = st.date_input(
        "Roster Period:",
        value=[date.today(), date.today() + timedelta(days=13)], # Default 2 weeks
    )

    if st.button("🚀 Generate Roster"):
        if not st.session_state.employees:
            st.error("Please upload an Excel file first!")
        elif len(date_range) != 2:
            st.error("Please select a valid start and end date.")
        else:
            start_dt, end_dt = date_range
            dates = get_date_list(start_dt, end_dt)
            solver = RosterSolver(st.session_state.employees, dates, st.session_state.holidays)
            
            with st.spinner("AI is optimising shifts..."):
                roster_df, summary_df, error_list = solver.solve()
                if roster_df is not None:
                    st.session_state.roster_df = roster_df
                    st.session_state.summary_df = summary_df
                    st.sidebar.success("Roster Generated!")
                else:
                    st.error("Roster Failed. Check availability.")
                    for err in error_list: st.write(err)

# --- MAIN CONTENT AREA ---
st.title("🗓️ Duty Roster Planner")

if st.session_state.roster_df is None:
    # --- WELCOME / PRE-SOLVE VIEW ---
    st.write("### Welcome! 👋")
    st.write("Use the sidebar on the left to upload your database and generate a new schedule.")
    
    if st.session_state.employees:
        st.divider()
        st.subheader("Personnel Status Overview")
        display_data = []
        for e in st.session_state.employees:
            display_data.append({
                "Name": e.name, "Role": e.role.value, "YTD Points": e.ytd_points,
                "PH Status": "🛡️ Immune" if e.is_immune(date.today()) else "✅ Available",
                "Last PH": e.last_ph_date.strftime('%Y-%m-%d') if e.last_ph_date else "Never"
            })
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

else:
    # --- POST-SOLVE DASHBOARD ---
    tab1, tab2, tab3 = st.tabs(["📅 Schedule", "📊 Points Analytics", "💾 Finalise & Export"])

    with tab1:
        st.subheader("Optimised Weekly Schedule")
        st.dataframe(
            st.session_state.roster_df.sort_values(by="Date"),
            use_container_width=True, hide_index=True
        )
        
        # Download Roster Only
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            st.session_state.roster_df.to_excel(writer, index=False, sheet_name="Roster")
        st.download_button("📥 Download Roster (.xlsx)", buffer.getvalue(), f"Roster_{date.today()}.xlsx", "application/vnd.ms-excel")

    with tab2:
        st.subheader("Points Metrics")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("Point accumulation for this period:")
            st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)

        with col2:
            view_mode = st.radio("Visualise:", ["Points Earned (Current)", "Total Points (Historical)"], horizontal=True)
            target_col = "Points Earned" if "Current" in view_mode else "Total Points"
            
            df_plot = st.session_state.summary_df
            fig = go.Figure()
            
            fig.add_trace(go.Box(
                y=df_plot[target_col], 
                x=["Team"] * len(df_plot),  # Labels the x-axis "Team" for all points
                boxpoints='all',            # Show all data points
                jitter=0.4,                 # Adds a slight horizontal spread so points don't overlap
                pointpos=0,                 # <--- THIS CENTERS THE POINTS ON THE BOX
                marker=dict(
                    color="#ff4b4b",
                    size=8,
                    line=dict(width=1, color="white")
                ),
                line=dict(color="#333"),    # Darker lines for the box itself
                fillcolor="rgba(255, 75, 75, 0.4)", # Semi-transparent box
                text=df_plot["Employee"],
                name="Team Points"
            ))

            fig.update_layout(
                title=f"Score Spread: {target_col}",
                template="plotly_white",
                height=450,
                showlegend=False,
                yaxis_title="Points",
                xaxis_title=""
            )
            
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("💾 Save & Update Database")
        st.info("Clicking below will save this month's effort into memory.")
        
        # We need the path to the original file to update it
        # If using the uploaded file, we save it to a master path
        MASTER_PATH = os.path.join(DATA_FOLDER, "roster_database_updated.xlsx")

        if st.button("✅ Confirm Roster & Update History"):
            try:
                # 1. Load the original sheets
                all_sheets = pd.read_excel(TEMP_FILE_PATH, sheet_name=None)
                df_emp = all_sheets["Employees"]

                # 2. Map new totals to the YTD column
                point_map = dict(zip(st.session_state.summary_df["Employee"], 
                                     st.session_state.summary_df["Total Points"]))
                df_emp["YTD"] = df_emp["Name"].map(point_map).fillna(df_emp["YTD"])

                # 3. Update Last PH Date
                current_roster = st.session_state.roster_df
                # Filter for anyone who worked a PH shift
                ph_worked = current_roster[current_roster["Shift"].str.contains("PH", na=False)]
                for _, row in ph_worked.iterrows():
                    df_emp.loc[df_emp["Name"] == row["Employee"], "Last PH Date"] = row["Date"]

                # 4. Save to a new Buffer
                update_buffer = io.BytesIO()
                with pd.ExcelWriter(update_buffer, engine="xlsxwriter") as writer:
                    for sheet_name, df in all_sheets.items():
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Store in session state so the download button can see it
                st.session_state.final_database = update_buffer.getvalue()
                st.success("Database history updated! Download the new version below.")

            except Exception as e:
                st.error(f"Error during finalization: {e}")

        # The download button appears ONLY if the final_database exists in session state
        if "final_database" in st.session_state:
            st.divider()
            st.download_button(
                label="📥 Download Updated Master Database",
                data=st.session_state.final_database,
                file_name=f"Master_Database_Updated_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )