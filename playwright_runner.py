import streamlit as st
import subprocess
import os
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from fpdf import FPDF
import time
import altair as alt
import matplotlib.pyplot as plt
import requests   # for API mode

TESTS_DIR = r"D:\PlaywrightUI\tests"
REPO_PATH = r"D:\PlaywrightUI"   # local clone of your GitHub repo
REMOTE_NAME = "origin"
BRANCH_NAME = "main"

# --- Sidebar for Mode Selection ---
st.sidebar.title("⚙️ Execution Settings")
execution_mode = st.sidebar.selectbox(
    "Select Execution Mode:",
    options=["UI", "API"],
    index=0
)

execution_name = st.sidebar.text_input("Execution Name:", value="TestExecution")

st.title(f"🎭 Playwright Test Runner ({execution_mode} Mode) with PDF Report & Git Push")

scripts = [f for f in os.listdir(TESTS_DIR) if f.endswith(".py")]
script_config = {}

st.markdown("### Configure scripts, threads, iterations, and wait time")
num_scripts = st.number_input("How many scripts do you want to run?", min_value=1, max_value=10, value=1, step=1)

for idx in range(num_scripts):
    st.markdown(f"#### Script {idx+1}")
    cols = st.columns([2, 1, 1, 1])
    with cols[0]:
        script = st.selectbox(f"Select script {idx+1}", scripts, key=f"script_{idx}")
    with cols[1]:
        threads = st.number_input("Threads", min_value=1, max_value=20, value=1, step=1, key=f"{script}_threads_{idx}")
    with cols[2]:
        iterations = st.number_input("Iterations", min_value=1, max_value=50, value=1, step=1, key=f"{script}_iterations_{idx}")
    with cols[3]:
        wait_time = st.number_input("Wait Time (sec)", min_value=0, max_value=60, value=0, step=1, key=f"{script}_wait_{idx}")
    script_config[script] = (threads, iterations, wait_time)

def run_script(script, thread_id, iteration_id, wait_time, mode="UI"):
    if mode == "UI":
        result = subprocess.run(
            ["python", script],
            capture_output=True,
            text=True,
            cwd=TESTS_DIR
        )
    else:  # API mode
        try:
            response = requests.get(f"http://localhost:5000/run?script={script}")
            result = type("Result", (), {})()
            result.stdout = response.text
            result.stderr = ""
        except Exception as e:
            result = type("Result", (), {})()
            result.stdout = ""
            result.stderr = str(e)
    
    if wait_time > 0:
        time.sleep(wait_time)
    return script, thread_id, iteration_id, result

def generate_pdf_report(final_df, start_time, end_time, exec_name, chart_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Execution Report - {exec_name}", ln=True, align="C")
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Mode: {execution_mode}", ln=True)
    pdf.cell(200, 10, txt=f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"Total Duration: {str(end_time - start_time)}", ln=True)
    pdf.ln(10)

    col_widths = [80, 50, 50]
    headers = ["Transaction", "Avg Response Time (s)", "Total Executions"]
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1)
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for _, row in final_df.iterrows():
        y_before = pdf.get_y()
        x_before = pdf.get_x()
        pdf.multi_cell(col_widths[0], 10, str(row["Step"]), border=1)
        y_after = pdf.get_y()
        row_height = y_after - y_before
        pdf.set_xy(x_before + col_widths[0], y_before)
        pdf.multi_cell(col_widths[1], 10, f"{row['Avg_Response_Time']:.2f}", border=1)
        pdf.set_xy(x_before + col_widths[0] + col_widths[1], y_before)
        pdf.multi_cell(col_widths[2], 10, str(row["Total_Executions"]), border=1)
        pdf.set_y(y_before + row_height)

    pdf.ln(10)
    pdf.cell(200, 10, txt="Average Response Time Chart", ln=True, align="C")
    pdf.image(chart_path, x=10, y=None, w=180)

    pdf_file = os.path.join(REPO_PATH, f"{exec_name}_{execution_mode}.pdf")
    pdf.output(pdf_file)
    return pdf_file

def push_to_github(pdf_file, repo_path, commit_message="Add execution report"):
    try:
        subprocess.run(["git", "-C", repo_path, "add", pdf_file], check=True)
        subprocess.run(["git", "-C", repo_path, "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "-C", repo_path, "push", REMOTE_NAME, BRANCH_NAME], check=True)
        st.success("✅ Report pushed to GitHub successfully!")
    except subprocess.CalledProcessError as e:
        st.error(f"❌ Git error: {e}")

if st.button("Run Scripts"):
    if not script_config:
        st.warning("Please configure at least one script.")
    else:
        start_time = datetime.now()
        script_results = {script: [] for script in script_config.keys()}

        with ThreadPoolExecutor() as executor:
            futures = []
            for script, (threads, iterations, wait_time) in script_config.items():
                for t in range(1, threads+1):
                    for i in range(1, iterations+1):
                        futures.append(executor.submit(run_script, script, t, i, wait_time, execution_mode))

            for future in as_completed(futures):
                script, thread_id, iteration_id, result = future.result()
                steps_output = result.stdout.strip()
                if steps_output:
                    try:
                        steps = json.loads(steps_output)
                        df = pd.DataFrame(steps)
                        df["Response Time (s)"] = pd.to_numeric(df["Response Time (s)"], errors="coerce")
                        script_results[script].append(df)
                    except json.JSONDecodeError:
                        st.warning(f"Could not parse step timings for {script}.")
                else:
                    st.warning(f"No step timings found for {script} (Thread {thread_id}, Iteration {iteration_id}).")

                if result.stderr.strip():
                    with st.expander(f"Error logs for {script}"):
                        st.error(result.stderr)

        end_time = datetime.now()

        combined_all = []
        for script, dfs in script_results.items():
            if dfs:
                combined = pd.concat(dfs, ignore_index=True)
                avg_df = combined.groupby("Step")["Response Time (s)"].agg(
                    Avg_Response_Time="mean",
                    Total_Executions="count"
                ).reset_index()
                combined_all.append(avg_df)

        if combined_all:
            final_df = pd.concat(combined_all, ignore_index=True)

            st.markdown("## 📊 Execution Summary")
            display_df = final_df.copy()
            display_df["Avg_Response_Time"] = display_df["Avg_Response_Time"].map(lambda x: f"{x:.2f}")
            st.dataframe(display_df)

            chart = alt.Chart(final_df).mark_bar().encode(
                x=alt.X("Step:N", sort=None, title="Transaction Name"),
                y=alt.Y("Avg_Response_Time:Q", title="Average Response Time (s)"),
                color="Step:N",
                tooltip=["Step", "Avg_Response_Time", "Total_Executions"]
            ).properties(title="Average Response Time per Transaction").interactive()

            st.altair_chart(chart, use_container_width=True)

            fig, ax = plt.subplots(figsize=(8, 4))
            colors = plt.cm.tab20.colors
            final_df.plot(kind="bar", x="Step", y="Avg_Response_Time", ax=ax, color=colors)
            ax.set_ylabel("Avg Response Time (s)")
            ax.set_xlabel("Transaction Name")
            ax.set_title("Average Response Time per Transaction")
            chart_path = os.path.join(REPO_PATH, "chart.png")
            plt.tight_layout()
            plt.savefig(chart_path)

            pdf_file = generate_pdf_report(final_df, start_time, end_time, execution_name, chart_path)

            # 📥 Download button for PDF
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="📥 Download Execution Report (PDF)",
                    data=f,
                    file_name=os.path.basename(pdf_file),
                    mime="application/pdf"
                )

            # 🚀 Push to GitHub
            if st.button("🚀 Push Report to GitHub"):
                push_to_github(pdf_file, REPO_PATH)
