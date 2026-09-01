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

TESTS_DIR = r"D:\PlaywrightUI\tests"
REPO_PATH = r"D:\PlaywrightUI"
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

# --- Config UI ---
if execution_mode == "UI":
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

else:  # API mode
    st.markdown("### Configure API scripts, SLA, threads, iterations, and wait time")
    num_scripts = st.number_input("How many API scripts do you want to run?", min_value=1, max_value=10, value=1, step=1)

    for idx in range(num_scripts):
        st.markdown(f"#### API Script {idx+1}")
        cols = st.columns([2, 1, 1, 1, 1])
        with cols[0]:
            script = st.selectbox(f"Select API script {idx+1}", scripts, key=f"api_script_{idx}")
        with cols[1]:
            sla = st.number_input("SLA Threshold (s)", min_value=0.1, max_value=10.0, value=2.0, step=0.1, key=f"{script}_sla_{idx}")
        with cols[2]:
            threads = st.number_input("Threads", min_value=1, max_value=20, value=1, step=1, key=f"{script}_threads_api_{idx}")
        with cols[3]:
            iterations = st.number_input("Iterations", min_value=1, max_value=50, value=1, step=1, key=f"{script}_iterations_api_{idx}")
        with cols[4]:
            wait_time = st.number_input("Wait Time (sec)", min_value=0, max_value=60, value=0, step=1, key=f"{script}_wait_api_{idx}")
        script_config[script] = (sla, threads, iterations, wait_time)

# --- Script runners ---
def run_script_api(script, thread_id, iteration_id, sla_threshold, wait_time):
    start = time.time()
    result = subprocess.run(
        ["python", script, "1"],  # pass iteration count if needed
        capture_output=True,
        text=True,
        cwd=TESTS_DIR
    )
    end = time.time()
    duration = end - start

    transaction_name = script
    http_status = None

    try:
        steps_output = result.stdout.strip()
        if steps_output:
            steps = json.loads(steps_output)
            if isinstance(steps, list) and len(steps) > 0:
                transaction_name = steps[0].get("Step", script)
                http_status = steps[0].get("HTTP Code", None)
    except Exception:
        pass

    # ✅ SLA based on HTTP status code (200 or 201 = Pass)
    sla_result = "Pass" if http_status in [200, 201] else "Fail"

    record = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Transaction": transaction_name,
        "Thread": thread_id,
        "Iteration": iteration_id,
        "Response Time (s)": round(duration, 2),
        "SLA": sla_result,
        "HTTP status code": http_status
    }
    if wait_time > 0:
        time.sleep(wait_time)
    return record

# --- PDF Report ---
def generate_pdf_report(summary_df, start_time, end_time, exec_name, chart_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.cell(200, 10, txt=f"Execution Report - {exec_name}", ln=True, align="C")
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Mode: {execution_mode}", ln=True)
    pdf.cell(200, 10, txt=f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(200, 10, txt=f"Total Duration: {str(end_time - start_time)}", ln=True)
    pdf.ln(10)

    # Summary table
    headers = list(summary_df.columns)
    col_widths = [200 // len(headers)] * len(headers)

    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1)
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for _, row in summary_df.iterrows():
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, str(row[header]), border=1)
        pdf.ln()

    pdf.ln(10)
    pdf.cell(200, 10, txt="Charts (Pass Only)", ln=True, align="C")
    pdf.image(chart_path, x=10, y=None, w=180)

    pdf_file = os.path.join(REPO_PATH, f"{exec_name}_{execution_mode}_summary.pdf")
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

# --- Run Scripts ---
if st.button("Run Scripts"):
    start_time = datetime.now()

    if execution_mode == "UI":
        st.warning("UI mode unchanged in this version.")
    else:  # --- API Mode ---
        results = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for script, (sla, threads, iterations, wait_time) in script_config.items():
                for t in range(1, threads+1):
                    for i in range(1, iterations+1):
                        futures.append(executor.submit(run_script_api, script, t, i, sla, wait_time))
            for future in as_completed(futures):
                results.append(future.result())

        end_time = datetime.now()
        if results:
            final_df = pd.DataFrame(results)

                        # Compute TPM based only on Pass executions
            pass_execs = final_df[final_df["SLA"] == "Pass"]
            total_pass_execs = len(pass_execs)
            total_duration = (end_time - start_time).total_seconds() / 60
            tpm = round(total_pass_execs / total_duration, 2) if total_duration > 0 else 0

            # --- Aggregated summary per Transaction ---
            summary_df = (
                final_df.groupby("Transaction")
                .agg(
                    Total_Threads_Executed=("Thread", "nunique"),
                    Avg_Response_Time_s=("Response Time (s)", "mean"),
                    Pass_Count=("SLA", lambda x: (x == "Pass").sum()),
                    Fail_Count=("SLA", lambda x: (x == "Fail").sum())
                )
                .reset_index()
            )

            # Add TPM (global, based on Pass count only)
            summary_df["TPM"] = tpm

            # --- Show summary table ---
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            # --- Raw results download ---
            raw_csv = final_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Raw Results (CSV)",
                data=raw_csv,
                file_name=f"{execution_name}_raw_results.csv",
                mime="text/csv"
            )

            # --- Chart based on Pass executions only ---
            pass_df = final_df[final_df["SLA"] == "Pass"]

            chart = alt.Chart(pass_df).mark_bar().encode(
                x=alt.X("Transaction:N", title="Transaction Name"),
                y=alt.Y("Response Time (s):Q", title="Average Response Time (s)"),
                tooltip=["Timestamp", "Transaction", "Thread", "Iteration", "Response Time (s)", "HTTP status code"]
            ).properties(title="API Performance Summary (Pass Only)").interactive()

            st.altair_chart(chart, use_container_width=True)

            # --- Matplotlib chart (Pass only, fix for numeric data issue) ---
            fig, ax = plt.subplots(figsize=(8, 4))
            avg_pass_df = pass_df.groupby("Transaction", as_index=False)["Response Time (s)"].mean()
            avg_pass_df.plot(
                kind="bar",
                x="Transaction",
                y="Response Time (s)",
                ax=ax,
                color="skyblue",
                legend=False
            )
            ax.set_ylabel("Avg Response Time (s)")
            ax.set_xlabel("Transaction Name")
            ax.set_title("API Performance Summary (Pass Only)")
            chart_path = os.path.join(REPO_PATH, "chart.png")
            plt.tight_layout()
            plt.savefig(chart_path)

            # --- Generate PDF report ---
            pdf_file = generate_pdf_report(summary_df, start_time, end_time, execution_name, chart_path)

            with open(pdf_file, "rb") as f:
                    st.download_button(
                        label="📥 Download Summary Report (PDF)",
                        data=f,
                        file_name=os.path.basename(pdf_file),
                        mime="application/pdf"
                    )

            if st.button("🚀 Push Report to GitHub"):
                    push_to_github(pdf_file, REPO_PATH)
