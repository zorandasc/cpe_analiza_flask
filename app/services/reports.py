import os
from datetime import date, datetime
from collections import defaultdict
from flask import render_template, current_app
from app.extensions import db
from app.utils.dates import get_current_week_friday
from app.models import ReportSetting, ReportRecipients
from app.services.email_service import send_email
from app.services.admin import (
    get_cpe_inventory_chart_data,
    get_cpe_dismantle_chart_data,
    get_stb_inventory_chart_data,
    get_iptv_inventory_chart_data,
    get_ont_inventory_chart_data,
)


def run_weekly_report_job():
    # Get settins for sending weekly report
    settings = ReportSetting.query.first()

    if not settings or not settings.enabled:
        return "Disabled"

    now = datetime.now()

    # now.weekday() ide od 0
    if now.weekday() + 1 != settings.send_day:
        return "Wrong day"

    if now.time() < settings.send_time:
        return "Too early"

    # prevents duplicates
    # safe even if cron restarts
    if settings.last_sent_at and settings.last_sent_at.date() == now.date():
        return "Already sent"

    # FORGE EMAIL TO SEND
    recipients = [r.email for r in ReportRecipients.query.filter_by(active=True).all()]

    if not recipients:
        return "No recipients"

    pdf_path = generate_pdf()

    body_text = """
        Dragi Svi,

        U prilogu Vam dostavljamo sedmični izvještaj o inventaru CPE opreme.

        Sažetak:
        - Pregled stanja ukupne, raspoložive i demontirane CPE opreme
        - Značajne sedmične promjene
        - Analiza trendova

        S poštovanjem,
        Automatizovani sistem izvještavanja
    """

    body_html = """
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <p>Dragi Svi,</p>
                    
                    <p>U prilogu Vam dostavljamo sedmični izvještaj o inventaru <strong>CPE opreme</strong>.</p>
                    
                    <p><strong>Sažetak:</strong></p>
                    <ul style="list-style-type: disc; margin-left: 20px;">
                        <li>Pregled stanja ukupne, raspoložive i demontirane CPE opreme</li>
                        <li>Značajne sedmične promjene</li>
                        <li>Analiza trendova</li>
                    </ul>
                    
                    <p>S poštovanjem,<br>
                    <em>Automatizovani sistem izvještavanja</em></p>
                </body>
            </html>
    """
    # OR BUILD EMAIL  BODY VIA TEMPLATE:
    # body_html = render_template(
    # "emails/weekly_report.html",
    # total=this_week_total,
    # delta=cpe_total_delta,)

    # SEND EMAIL TO RECIPIENTS
    send_email(
        pdf_path=pdf_path,
        recipients=recipients,
        subject="Sedmični izvještaj o CPE inventaru",
        body_text=body_text,
        body_html=body_html,
    )

    settings.last_sent_at = datetime.now()
    db.session.commit()

    return "Sent"


def generate_pdf():
    # Lazy Load this heavy library
    from weasyprint import HTML

    current_week_end = get_current_week_friday()

    # data that will be passed to template (pdf)
    data = {"week": current_week_end.strftime("%d-%m-%Y"), "today": date.today()}

    # ----------------------------------------------
    # PULL DATA TO RENDER SUMMARY AND CHARTS
    # -------------------------------------------------
    cpe_data_total = get_cpe_inventory_chart_data(
        city_id=None, cpe_id=None, cpe_type=None, weeks=5
    )

    cpe_data_warehouse = get_cpe_inventory_chart_data(
        city_id=13, cpe_id=None, cpe_type=None, weeks=5
    )

    cpe_dismantle_data_total = get_cpe_dismantle_chart_data(
        city_id=None, cpe_id=None, cpe_type=None, dismantle_type_id=None, weeks=5
    )

    stb_data_total = get_stb_inventory_chart_data(stb_type_id=None, weeks=5)

    iptv_data_total = get_iptv_inventory_chart_data(weeks=5)

    ont_data_total = get_ont_inventory_chart_data(city_id=None, months=5)

    # ----------------------------------------------
    # SUMMARY SECTION
    # -------------------------------------------------

    # summary for cpe
    cpe_current_total = sum(row["data"][-2] for row in cpe_data_total["datasets"])

    cpe_previous_total = sum(row["data"][-1] for row in cpe_data_total["datasets"])

    cpe_current_warehouse = sum(
        row["data"][-2] for row in cpe_data_warehouse["datasets"]
    )

    cpe_previous_warehouse = sum(
        row["data"][-1] for row in cpe_data_warehouse["datasets"]
    )

    # summary for dismantle
    dismantle_current_total = sum(
        row["data"][-1] for row in cpe_dismantle_data_total["datasets"]
    )
    dismantle_previous_total = sum(
        row["data"][-2] for row in cpe_dismantle_data_total["datasets"]
    )

    # summary for stb
    stb_current_total = sum(row["data"][-1] for row in stb_data_total["datasets"])
    stb_previous_total = sum(row["data"][-2] for row in stb_data_total["datasets"])

    # summary for iptv
    iptv_current_total = sum(row["data"][-1] for row in iptv_data_total["datasets"])
    iptv_previous_total = sum(row["data"][-2] for row in iptv_data_total["datasets"])

    # summary for ont
    ont_current_total = sum(row["data"][-1] for row in ont_data_total["datasets"])
    ont_previous_total = sum(row["data"][-2] for row in ont_data_total["datasets"])

    data["summary"] = {
        "cpe": {
            "total": {
                "current": cpe_current_total,
                "previous": cpe_previous_total,
                "delta": cpe_current_total - cpe_previous_total,
            },
            "warehouse": {
                "current": cpe_current_warehouse,
                "previous": cpe_previous_warehouse,
                "delta": cpe_current_warehouse - cpe_previous_warehouse,
            },
        },
        "dismantle": {
            "current": dismantle_current_total,
            "previous": dismantle_previous_total,
            "delta": dismantle_current_total - dismantle_previous_total,
        },
        "stb": {
            "current": stb_current_total,
            "previous": stb_previous_total,
            "delta": stb_current_total - stb_previous_total,
        },
        "iptv": {
            "current": iptv_current_total,
            "previous": iptv_previous_total,
            "delta": iptv_current_total - iptv_previous_total,
        },
        "ont": {
            "current": ont_current_total,
            "previous": ont_previous_total,
            "delta": ont_current_total - ont_previous_total,
        },
    }

    significant_changes = []

    significant_changes += get_significant_changes(
        datasets=cpe_data_total["datasets"], source="CPE oprema u radu"
    )

    significant_changes += get_significant_changes(
        datasets=cpe_data_warehouse["datasets"], source="Raspoloživa CPE Oprema"
    )

    significant_changes += get_significant_changes(
        datasets=cpe_dismantle_data_total["datasets"],
        source="Demontirana CPE oprema",
    )

    grouped_changes = group_changes_by_source(significant_changes)

    data["significant_changes"] = grouped_changes

    # ----------------------------------------------
    # CHART SECTION
    # -------------------------------------------------
    # "cpe_chart_image" will be referenced in html template by img
    # build_report_char() will: build chart, save it as png and
    # return path to that saved image:
    # "cpe_chart_image": "static/reports/charts/cpe_trend.png",
    data["cpe_chart_image"] = build_report_chart(
        chart_data=cpe_data_total,
        output_filename="cpe_trend.png",
        title="Trend ukupne CPE opreme u radu po svim IJ I skladištima (Zadnjih 5 sedmica)",
    )

    # "cpe_dismantle_chart_image": "static/reports/charts/cpe_dismantle_trend.png",
    data["cpe_dismantle_chart_image"] = build_report_chart(
        chart_data=cpe_dismantle_data_total,
        output_filename="cpe_dismantle_trend.png",
        title="Trend ukupne demontirane CPE opreme po svim IJ (Zadnjih 5 sedmica)",
    )

    # "stb_chart_image"": "static/reports/charts/stb_chart_image"",
    data["stb_chart_image"] = build_report_chart(
        chart_data=stb_data_total,
        output_filename="stb_trend.png",
        title="Trend ukupne STB opreme u radu, IPTV platforma (Zadnjih 5 sedmica)",
    )

    # "iptv_chart_image": "static/reports/charts/iptv_trend.png",
    data["iptv_chart_image"] = build_report_chart(
        chart_data=iptv_data_total,
        output_filename="iptv_trend.png",
        title="Trend IPTV korisnika, IPTV platforma (Zadnjih 5 sedmica)",
    )

    # "ont_chart_image": "static/reports/charts/ont_trend.png",
    data["ont_chart_image"] = build_report_chart(
        chart_data=ont_data_total,
        output_filename="ont_trend.png",
        title="Trend ukupne ONT opreme u radu po svim IJ (Zadnjih 5 mijeseci)",
    )

    # for key, value in data.items():
    #    print(f"{key}: {value}")

    # ----4. Generate htm template with embeded data--------
    html = render_template("reports/pdf_report.html", **data)

    # ----5. Generate pdf file using weasyprint-----------------
    # base_url=current_app.root_path resolve path to css and images
    pdf = HTML(string=html, base_url=current_app.root_path).write_pdf()

    # ----6. Save pdf to static folder----------------------
    # path to .pdf file to write
    output_path = os.path.join(
        current_app.root_path, "generated_reports", "weekly_report.pdf"
    )

    with open(output_path, "wb") as f:
        f.write(pdf)

    # RETRUN PATH TO SAVED PDF
    return output_path


# ---------------
# HELPER FUNCTION FOR GENERATING PDF FILE
# --------------------
# using matplotlib to generate headless charts and save it as png to path
def generate_chart_image(title, labels, datasets, output_path):
    # On servers (Linux, Docker, RunPod, etc.) you MUST force a non-GUI backend.
    # Otherwise your app will crash in headless environments.
    import matplotlib

    matplotlib.use("Agg")

    # Lazy Load this heavy library matplotlib
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    plt.title(title)
    plt.xlabel("Sedmica")
    plt.ylabel("Količina")

    for dataset in datasets:
        plt.plot(labels, dataset["data"], label=dataset.get("label", ""))

    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


# build_report_char() will: build chart, save it as png and
# return path to that saved image:
def build_report_chart(chart_data, output_filename, title):
    # 1. Get chart data. chart_data holds labels and datasets
    # (**) Used to unpack a dictionary into keyword arguments
    # chart_data = chart_data_fn(**(chart_kwargs or {}))

    # 2. Define path where chart image will be save
    output_path = os.path.join(
        current_app.root_path,
        "static/reports/charts",
        output_filename,
    )

    # 3. Rendered chart_data as chart using matplotlib and than save the chart as png to path
    generate_chart_image(
        title=title,
        labels=chart_data["labels"],
        datasets=chart_data["datasets"],
        output_path=output_path,
    )

    # return path of saved chart image
    return f"static/reports/charts/{output_filename}"


def get_significant_changes(
    datasets,
    source,
    threshold=1000,
):
    changes = []
    for ds in datasets:
        diff = ds["data"][-1] - ds["data"][-2]

        if abs(diff) >= threshold:  # threshold
            changes.append(
                {
                    "source": source,
                    "equipment": ds["label"],
                    "diff": diff,
                    "direction": "up" if diff > 0 else "down",
                    "absolute": abs(diff),
                }
            )

    return changes


def group_changes_by_source(changes):
    # WE WANT TO GROUP BY SOURCE DATA INSIDE data["significant_changes"]
    # data["significant_changes"] = [
    # {"source": "CPE ukupno", "equipment": "ONT Huawei", "diff": 84},
    # {"source": "CPE ukupno", "equipment": "STB DTH", "diff": -41},
    # {"source": "STB IPTV", "equipment": "VIP5305", "diff": 62},]
    grouped = defaultdict(list)
    for change in changes:
        grouped[change["source"]].append(change)

    return dict(grouped)
