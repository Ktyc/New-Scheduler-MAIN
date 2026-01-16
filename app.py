import os
import streamlit as st
import pandas as pd
from src.io_handler import load_employees
from src.io_handler import load_holidays
from datetime import timedelta, date
from src.solver import RosterSolver
from typing import List
import io
import plotly.express as px
import plotly.graph_objects as go

if 'roster_df' not in st.session_state:
    st.session_state.roster_df = None
if 'summary_df' not in st.session_state:
    st.session_state.summary_df = None
if 'update_success' not in st.session_state:
    st.session_state.update_success = False

def get_date_list(start_date: date, end_date: date) -> List[date]:
    if start_date > end_date:
        return []
    
    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]

def set_view_report():
    st.session_state.active_view = "📊 Points Fairness Report"

st.set_page_config(page_title="Duty Roster Planner", layout="wide")
st.title("🗓️ Duty Roster Planner")


#Make data foler if it does not exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "data")
TEMP_FILE_PATH = os.path.join(DATA_FOLDER, "temp_data.xlsx")
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

uploaded_file = st.file_uploader("Upload Employee Excel", type=["xlsx"])

if uploaded_file:
    with open(TEMP_FILE_PATH, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    employees = load_employees(TEMP_FILE_PATH)
    public_holidays = load_holidays(TEMP_FILE_PATH)

    st.subheader("2. Select Date Range")
    date_range = st.date_input(
        "Select the period you want to roster:",
        value=[date.today(), date.today() + timedelta(days=6)],
        min_value=date.today() - timedelta(days=365),
        max_value=date.today() + timedelta(days=365)
    )

    if len(date_range) == 2:
        start_dt, end_dt = date_range
        dates = get_date_list(start_dt, end_dt)
        st.info(f"Generating roster for {len(dates)} days.")

        if st.button("🚀 Generate Roster"):
            solver = RosterSolver(employees, dates, public_holidays)
            
            with st.spinner("The AI is working on the best schedule..."):
                roster_df, summary_df, error_list = solver.solve()
                st.session_state.roster_df = roster_df
                st.session_state.summary_df = summary_df
                
            if st.session_state.roster_df is None:
                if error_list:
                    st.error("### 🛑 Roster Generation Failed")
                    for error in error_list:
                        st.write(error)
                    st.info("💡 **Tips to fix:** Check if too many people blacked out the same holiday, or if a specific employee has 0 availability in the database.")

        if st.session_state.roster_df is not None:
            st.success("Roster Optimized!")
            if "active_view" not in st.session_state:
                st.session_state.active_view = "📅 Final Schedule"
            if "view_mode" not in st.session_state:
                st.session_state.view_mode = "Current Roster Effort (Points Earned)"

            active_view = st.radio(
                "Navigation",
                ["📅 Final Schedule", "📊 Points Fairness Report"],
                key="active_view",
                horizontal=True,
                label_visibility="collapsed",
            )
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            DATA_FOLDER = os.path.join(BASE_DIR, "data")
            MASTER_PATH = os.path.join(DATA_FOLDER, "roster_database_random.xlsx")

            if active_view == "📅 Final Schedule":
                st.dataframe(
                    st.session_state.roster_df.sort_values(by="Date"),
                    use_container_width=True,
                    hide_index=True,
                )

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    st.session_state.roster_df.to_excel(writer, index=False, sheet_name="Monthly Roster")

                st.download_button(
                    label="📥 Download Roster (.xlsx)",
                    data=buffer.getvalue(),
                    file_name=f"Roster_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_roster_btn",
                )

            else:
                st.write("This table shows the point distribution including YTD history.")
                st.dataframe(st.session_state.summary_df, use_container_width=True)

                view_mode = st.radio(
                    "Select Metric to Visualize:",
                    ["Current Roster Effort (Points Earned)", "Historical Fairness (Total Points)"],
                    key="view_mode",
                    horizontal=True,
                )

                target_col = "Points Earned" if "Effort" in view_mode else "Total Points"

                if "summary_df" in st.session_state and st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
                    df_plot = st.session_state.summary_df.copy()

                    fig = go.Figure()
                    fig.add_trace(
                        go.Box(
                            y=df_plot[target_col],
                            name="Team",
                            boxpoints="all",
                            jitter=0.5,
                            pointpos=0,
                            marker=dict(
                                color="rgba(31, 119, 180, 0.7)",
                                size=10,
                                line=dict(width=1.5, color="white"),
                            ),
                            line=dict(width=2, color="#1f77b4"),
                            fillcolor="rgba(31, 119, 180, 0.2)",
                            text=df_plot["Employee"],
                            hoverinfo="text+y",
                            hovertemplate="<b>%{text}</b><br>Points: %{y}<extra></extra>",
                        )
                    )
                    if target_col == "Total Points":
                        mean_val = df_plot[target_col].mean()
                        fig.add_hline(
                            y=mean_val,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"Avg: {mean_val:.2f}",
                        )
                    fig.update_layout(
                        title=f"Distribution: {target_col}",
                        yaxis_title="Points Value",
                        template="plotly_white",
                        height=600,
                        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                        margin=dict(l=80, r=80, t=80, b=50),
                        hovermode="closest",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.info("Run the solver to generate data.")

                if st.button("Finalise & Update Employee Data", key="finalise_update_btn", on_click=set_view_report):

                    try:
                        all_sheets = pd.read_excel(MASTER_PATH, sheet_name=None)
                        df_emp = all_sheets["Employees"]  # reference into dict

                        # Update YTD points
                        point_map = dict(
                            zip(
                                st.session_state.summary_df["Employee"],
                                st.session_state.summary_df["Total Points"],
                            )
                        )
                        df_emp["YTD"] = df_emp["Name"].map(point_map).fillna(df_emp["YTD"])

                        # Update Last PH Date for employees who worked PH in current roster
                        current_roster = st.session_state.roster_df
                        ph_worked = current_roster[current_roster["Shift"].str.contains("PH", na=False)]
                        for _, row in ph_worked.iterrows():
                            df_emp.loc[df_emp["Name"] == row["Employee"], "Last PH Date"] = row["Date"]
                        today = date.today()
                        years_threshold = 2

                        def calculate_status(last_date):
                            if pd.isna(last_date):
                                return "Available"
                            last_dt = pd.to_datetime(last_date)
                            try:
                                expiry = last_dt.replace(year=last_dt.year + years_threshold)
                            except ValueError:
                                expiry = last_dt.replace(year=last_dt.year + years_threshold, day=28)
                            return "Immune" if pd.Timestamp(today) < expiry else "Available"

                        df_emp["PH_Status"] = df_emp["Last PH Date"].apply(calculate_status)

                        # Write ALL sheets back to a single downloadable file
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                            for sheet_name, df in all_sheets.items():
                                df.to_excel(writer, sheet_name=sheet_name, index=False)

                        st.session_state.final_file = buffer.getvalue()
                        st.session_state.update_success = True
                        st.success("Points updated! You can now download the new Master File below.")

                    except Exception as e:
                        st.error(f"Error updating points: {e}")

                if "final_file" in st.session_state:
                    st.download_button(
                        label="📥 Download Updated Employee Database",
                        data=st.session_state.final_file,
                        file_name=f"Employee_Database_Updated_{date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_updated_db_btn",
                    )
            
                    
    display_data = []
    
    for e in employees:
        is_currently_immune = e.is_immune(date.today())                   
        immunity_status = "🛡️ Immune" if is_currently_immune else "✅ Available"
        
        display_data.append({
            "Name": e.name,
            "Role": e.role.value, 
            "YTD Points": e.ytd_points,
            "Blackouts": ", ".join([d.strftime('%Y-%m-%d') for d in e.blackouts]) if e.blackouts else "None", 
            "PH Bids": ", ".join([d.strftime('%Y-%m-%d') for d in e.ph_bids]) if e.ph_bids else "None",
            "Last PH Worked": e.last_ph_date.strftime('%Y-%m-%d') if e.last_ph_date else "Never",
            "PH Status": immunity_status
        })
    
    df_to_show = pd.DataFrame(display_data)
    
    st.subheader("Personnel Overview")
    st.dataframe(df_to_show, use_container_width=True)

