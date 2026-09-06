from fpdf import FPDF
import os


def safe_text(text):
    """Ensure text is Latin-1 safe for FPDF."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode("latin-1", "ignore").decode("latin-1")

def generate_pdf_report(summary_df, start_time, end_time, execution_name, chart_path, extra_chart=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Title
    pdf.cell(200, 10, txt=safe_text("Execution Report"), ln=True, align="C")
    pdf.ln(10)

    # Execution details
    pdf.cell(200, 10, txt=safe_text(f"Execution Name: {execution_name}"), ln=True)
    pdf.cell(200, 10, txt=safe_text(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"), ln=True)
    pdf.cell(200, 10, txt=safe_text(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"), ln=True)
    pdf.cell(200, 10, txt=safe_text(f"Total Duration: {str(end_time - start_time)}"), ln=True)
    pdf.ln(10)

    # --- Final Execution Results Header ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=safe_text("Final Execution Results"), ln=True, align="L")
    pdf.ln(5)

    # Fixed column widths
    col_widths = [50, 40, 50, 30, 30, 30]  # adjust as needed
    headers = ["Transaction", "Threads", "Avg Resp Time (s)", "Pass", "Fail", "TPM"]

    # Table header
    pdf.set_font("Arial", 'B', 10)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, safe_text(header), border=1, align="C")
    pdf.ln()

    # Table rows
    pdf.set_font("Arial", size=9)
    for _, row in summary_df.iterrows():
        row_data = [
            safe_text(row["Transaction"]),
            safe_text(row["Total_Threads_Executed"]),
            safe_text(f"{row['Avg_Response_Time_s']:.2f}"),
            safe_text(row["Pass_Count"]),
            safe_text(row["Fail_Count"]),
            safe_text(row["TPM"])
        ]
        for i, data in enumerate(row_data):
            x_before = pdf.get_x()
            y_before = pdf.get_y()
            pdf.multi_cell(col_widths[i], 10, data, border=1, align="C")
            pdf.set_xy(x_before + col_widths[i], y_before)
        pdf.ln()

    # Add charts
    if chart_path and os.path.exists(chart_path):
        pdf.image(chart_path, x=10, y=None, w=180)
    if extra_chart and os.path.exists(extra_chart):
        pdf.add_page()
        pdf.image(extra_chart, x=10, y=None, w=180)

    pdf_file = os.path.join(os.getcwd(), f"{execution_name}_summary.pdf")
    pdf.output(pdf_file)
    return pdf_file



def push_to_github(pdf_file, repo_path, commit_message="Add execution report"):
    """
    Pushes the generated PDF report to the configured GitHub repository.
    Assumes repo_path is a valid Git repo with a remote set.
    """
    try:
        # Stage the file
        subprocess.run(["git", "-C", repo_path, "add", pdf_file], check=True)

        # Commit changes
        subprocess.run(["git", "-C", repo_path, "commit", "-m", commit_message], check=True)

        # Push to remote (default: origin main)
        subprocess.run(["git", "-C", repo_path, "push", "origin", "main"], check=True)

        st.success("✅ Report pushed to GitHub successfully!")
    except subprocess.CalledProcessError as e:
        st.error(f"❌ Git error: {e}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")