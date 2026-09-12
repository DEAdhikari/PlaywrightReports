import streamlit as st
import subprocess
import os
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import time
import altair as alt
import matplotlib.pyplot as plt
from report_utils import generate_pdf_report, push_to_github

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

# --- Sidebar Run Mode for API ---
run_mode = None
execution_time = None
ramp_up_time = None
if execution_mode == "API":
    run_mode = st.sidebar.radio(
        "Select Run Mode:",
        options=["Run by Iterations", "Run by Time"],
        index=0,
        key="api_run_mode"
    )

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
        script_config[script] = (threads, iterations, wait_time, "iterations", 0)

else:  # API mode
    st.markdown("### Configure API scripts, SLA, threads, iterations/time, wait time, and ramp up")

    cols_top = st.columns([2, 2, 2])
    with cols_top[0]:
        num_scripts = st.number_input("Number of Scripts", min_value=1, max_value=10, value=1, step=1)
    with cols_top[1]:
        if run_mode == "Run by Time":
            execution_time = st.number_input("Execution Time (minutes)", min_value=1, max_value=120, value=5, step=1)
    with cols_top[2]:
        if run_mode == "Run by Time":
            ramp_up_time = st.number_input("Ramp Up Time (seconds)", min_value=0, max_value=60, value=0, step=1)

    for idx in range(num_scripts):
        st.markdown(f"#### API Script {idx+1}")
        if run_mode == "Run by Iterations":
            cols = st.columns([2, 1, 1, 1, 1])
        else:
            cols = st.columns([2, 1, 1, 1])

        with cols[0]:
            script = st.selectbox(f"Select API script {idx+1}", scripts, key=f"api_script_{idx}")
        with cols[1]:
            sla = st.number_input("SLA Threshold (s)", min_value=0.1, max_value=10.0, value=2.0, step=0.1, key=f"{script}_sla_{idx}")
        with cols[2]:
            threads = st.number_input("Threads", min_value=1, max_value=20, value=1, step=1, key=f"{script}_threads_api_{idx}")

        if run_mode == "Run by Iterations":
            with cols[3]:
                iterations = st.number_input("Iterations", min_value=1, max_value=50, value=1, step=1, key=f"{script}_iterations_api_{idx}")
            with cols[4]:
                wait_time = st.number_input("Wait Time (sec)", min_value=0, max_value=60, value=0, step=1, key=f"{script}_wait_api_{idx}")
            script_config[script] = (sla, threads, iterations, wait_time, "iterations", 0)
        else:
            with cols[3]:
                wait_time = st.number_input("Wait Time (sec)", min_value=0, max_value=60, value=0, step=1, key=f"{script}_wait_api_{idx}")
            script_config[script] = (sla, threads, execution_time, wait_time, "time", ramp_up_time)

# --- Script runners ---
def run_script_api(script, thread_id, iteration_id, sla_threshold, wait_time):
    start = time.time()
    result = subprocess.run(
        ["python", script, "1"],
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

# --- Run Scripts ---
if st.button("Run Scripts"):
    start_time = datetime.now()
    results = []
    for script, (sla, threads, value, wait_time, mode, ramp_up) in script_config.items():
        if mode == "iterations":
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(run_script_api, script, t, i, sla, wait_time)
                           for t in range(1, threads+1)
                           for i in range(1, value+1)]
                for future in as_completed(futures):
                    results.append(future.result())
        else:  # Run by Time
            end_time_limit = datetime.now() + timedelta(minutes=value)
            i = 1
            with ThreadPoolExecutor(max_workers=threads) as executor:
                while datetime.now() < end_time_limit:
                    futures = [executor.submit(run_script_api, script, t, i, sla, wait_time)
                               for t in range(1, threads+1)]
                    for future in as_completed(futures):
                        results.append(future.result())
                    if ramp_up > 0:
                        time.sleep(ramp_up)
                    i += 1
                    if wait_time > 0:
                        time.sleep(wait_time)

    end_time = datetime.now()

    if results:
        final_df = pd.DataFrame(results)
        pass_execs = final_df[final_df["SLA"] == "Pass"]
        total_pass_execs = len(pass_execs)
        total_duration = (end_time - start_time).total_seconds() / 60
        tpm = round(total_pass_execs / total_duration, 2) if total_duration > 0 else 0

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
        summary_df["TPM"] = tpm

                # Save in session state
        st.session_state["final_df"] = final_df
        st.session_state["summary_df"] = summary_df
        chart_path = os.path.join(REPO_PATH, "chart.png")
        time_series_chart_path = os.path.join(REPO_PATH, "time_series_chart.png")

        # Generate charts
        pass_df = final_df[final_df["SLA"] == "Pass"]
        chart = alt.Chart(pass_df).mark_bar().encode(
            x=alt.X("Transaction:N", title="Transaction Name"),
            y=alt.Y("Response Time (s):Q", title="Average Response Time (s)"),
            tooltip=["Timestamp", "Transaction", "Thread", "Iteration", "Response Time (s)", "HTTP status code"]
        ).properties(title="API Performance Summary (Pass Only)").interactive()
        st.session_state["altair_chart"] = chart

        fig, ax = plt.subplots(figsize=(8, 4))
        avg_pass_df = pass_df.groupby("Transaction", as_index=False)["Response Time (s)"].mean()
        avg_pass_df.plot(kind="bar", x="Transaction", y="Response Time (s)", ax=ax, color="skyblue", legend=False)
        ax.set_ylabel("Avg Response Time (s)")
        ax.set_xlabel("Transaction Name")
        ax.set_title("API Performance Summary (Pass Only)")
        plt.tight_layout()
        plt.savefig(chart_path)
        st.session_state["matplotlib_fig"] = fig

        # Time-series chart
        final_df["Elapsed Time (s)"] = (pd.to_datetime(final_df["Timestamp"]) - start_time).dt.total_seconds()
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        for txn_name, txn_group in final_df.groupby("Transaction"):
            ax2.plot(txn_group["Elapsed Time (s)"], txn_group["Response Time (s)"],
                     marker="o", linestyle="-", label=txn_name)
        ax2.set_xlabel("Elapsed Time (s)")
        ax2.set_ylabel("Response Time (s)")
        ax2.set_title("Response Time Trend by Transaction")
        ax2.legend(title="Transaction", bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        plt.savefig(time_series_chart_path)
        st.session_state["time_series_fig"] = fig2

        # Generate PDF report
        pdf_file = generate_pdf_report(summary_df, start_time, end_time,
                                       execution_name, chart_path, extra_chart=time_series_chart_path)
        st.session_state["pdf_file"] = pdf_file

# --- Display results if they exist in session state ---
if "summary_df" in st.session_state:
    st.markdown("## 📊 Final Execution Results")
    st.dataframe(st.session_state["summary_df"], use_container_width=True, hide_index=True)

    # Raw results download
    raw_csv = st.session_state["final_df"].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Raw Results (CSV)",
        data=raw_csv,
        file_name=f"{execution_name}_raw_results.csv",
        mime="text/csv"
    )

    # PDF download
    with open(st.session_state["pdf_file"], "rb") as f:
        st.download_button(
            label="📥 Download Summary Report (PDF)",
            data=f,
            file_name=os.path.basename(st.session_state["pdf_file"]),
            mime="application/pdf"
        )

    # Charts
    st.altair_chart(st.session_state["altair_chart"], use_container_width=True)
    st.pyplot(st.session_state["matplotlib_fig"])
    st.pyplot(st.session_state["time_series_fig"])

    # Push to GitHub
    if st.button("🚀 Push Report to GitHub"):
        push_to_github(st.session_state["pdf_file"], REPO_PATH)
