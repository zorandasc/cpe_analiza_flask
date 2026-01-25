from flask import render_template, current_app
import os


def generate_pdf():
    # Lazy Load this heavy library
    from weasyprint import HTML

    # pull data to render chart and summary tables
    data = {"week": "03/2026"}

    html = render_template("reports/weekly_report.html", **data)

    # base_url=current_app.root_path resolve path to css and images
    pdf = HTML(string=html, base_url=current_app.root_path).write_pdf()

    print(current_app.root_path)

    # path to .pdf file to write
    output_path = os.path.join(
        current_app.root_path, "generated_reports", "weekly_report.pdf"
    )

    with open(output_path, "wb") as f:
        f.write(pdf)

    return output_path


def send_email():
    pass
