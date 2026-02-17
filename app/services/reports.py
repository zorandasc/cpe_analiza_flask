import os
from datetime import date, datetime
from collections import defaultdict
from flask import render_template, current_app
from app.extensions import db
from app.utils.dates import get_current_week_friday
from app.models import ReportSetting, ReportRecipients, CpeTypeEnum
from app.services.email_service import send_email
from app.services.charts import (
    get_cpe_inventory_chart_data,
    get_cpe_dismantle_chart_data,
    get_stb_inventory_chart_data,
    get_iptv_inventory_chart_data,
    get_ont_inventory_chart_data,
)


def run_weekly_report_job():
    # Get settins from db for sending weekly report
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

    # ALL CPE TYPES FOR 5 WEEKS
    cpe_total = get_cpe_inventory_chart_data(
        city_id=None, cpe_id=None, cpe_type=None, weeks=10
    )

    # ALL CPE TYPES FOR 5 WEEKS
    cpe_warehouse_total = get_cpe_inventory_chart_data(
        city_id=13, cpe_id=None, cpe_type=None, weeks=10
    )

    # ALL CPE TYPES FOR 5 WEEKS
    cpe_dismantle_total = get_cpe_dismantle_chart_data(
        city_id=None, cpe_id=None, cpe_type=None, dismantle_type_id=None, weeks=10
    )

    # ALL STB TYPES FOR 5 WEEKS
    stb_total = get_stb_inventory_chart_data(stb_type_id=None, weeks=10)

    # ALL DATA FOR 5 WEEKS
    iptv_total = get_iptv_inventory_chart_data(weeks=10)

    # ALL DATA FOR 5 WEEKS
    ont_total = get_ont_inventory_chart_data(city_id=None, months=5)

    # ----------------------------------------------
    # SUMMARY SECTION (LAST 2 WEEKS) IN PDF REPORT
    # ------------------------------------------------
    target_labels = [CpeTypeEnum("IAD"), CpeTypeEnum("STB"), CpeTypeEnum("ONT")]

    cpe_total_summary = extract_current_previous_diff(
        cpe_total["datasets"], target_labels
    )

    cpe_warehouse_summary = extract_current_previous_diff(
        cpe_warehouse_total["datasets"], target_labels
    )

    cpe_dismantle_summary = extract_current_previous_diff(
        cpe_dismantle_total["datasets"], target_labels
    )

    stb_summary = extract_current_previous_diff(stb_total["datasets"], ["STB Uređaji"])

    iptv_summary = extract_current_previous_diff(
        iptv_total["datasets"], ["IPTV korisnici"]
    )

    ont_summary = extract_current_previous_diff(ont_total["datasets"], ["ONT uređaji"])

    # ADD TO DATA LIST TO ADD TO PDF
    data["summary"] = {
        "cpetotal": cpe_total_summary,
        "cpewarehouse": cpe_warehouse_summary,
        "cpedismantle": cpe_dismantle_summary,
        "stb": stb_summary,
        "iptv": iptv_summary,
        "ont": ont_summary,
    }

    # ----------------------------------------------
    # SIGNIFICANT CHANGES SECTION IN PDF REPORT
    # -------------------------------------------------

    significant_changes = []

    """
    significant_changes += get_significant_changes(
        datasets=cpe_total["datasets"], source="CPE oprema u radu"
    )

    significant_changes += get_significant_changes(
        datasets=cpe_warehouse_total["datasets"], source="CPE Oprema raspoloživa"
    )

    significant_changes += get_significant_changes(
        datasets=cpe_dismantle_total["datasets"],
        source="CPE oprema demontirana",
    )
    """
    grouped_changes = group_changes_by_source(significant_changes)

    data["significant_changes"] = grouped_changes

    # ----------------------------------------------
    # CHART SECTION IN PDF REPORT
    # -------------------------------------------------

    # build_report_char() will:
    # 1. build chart USING MATPLOTLIB,
    # 2. save it as .png FILE
    # 3. return path OF that saved image:
    # FOR EXAMPLE:
    # "cpe_chart_image": "static/reports/charts/cpe_trend.png",

    # "cpe_chart_image" will be referenced in html template by img HTML TAG
    data["cpe_chart_image"] = build_report_chart(
        chart_data=cpe_total,
        output_filename="cpe_trend.png",
        title="Trend ukupne CPE opreme po tipu (Zadnjih 10 sedmica)",
    )

    data["cpe_warehouse_chart_image"] = build_report_chart(
        chart_data=cpe_warehouse_total,
        output_filename="cpe_trend_raspoloziva.png",
        title="Trend CPE opreme u raspoloživa oprema po tipu (Zadnjih 10 sedmica)",
    )

    # "cpe_dismantle_chart_image": "static/reports/charts/cpe_dismantle_trend.png",
    data["cpe_dismantle_chart_image"] = build_report_chart(
        chart_data=cpe_dismantle_total,
        output_filename="cpe_dismantle_trend.png",
        title="Trend ukupne demontirane CPE opreme po tipu (Zadnjih 10 sedmica)",
    )

    # "stb_chart_image"": "static/reports/charts/stb_chart_image"",
    data["stb_chart_image"] = build_report_chart(
        chart_data=stb_total,
        output_filename="stb_trend.png",
        title="Trend ukupne STB opreme, IPTV platforma (Zadnjih 10 sedmica)",
    )

    # "iptv_chart_image": "static/reports/charts/iptv_trend.png",
    data["iptv_chart_image"] = build_report_chart(
        chart_data=iptv_total,
        output_filename="iptv_trend.png",
        title="Trend IPTV korisnika, IPTV platforma (Zadnjih 10 sedmica)",
    )

    # "ont_chart_image": "static/reports/charts/ont_trend.png",
    data["ont_chart_image"] = build_report_chart(
        chart_data=ont_total,
        output_filename="ont_trend.png",
        title="Trend ukupne ONT opreme, pristupn GPON mreža (Zadnjih 5 mijeseci)",
    )

    # ----------------------------------------------
    # BUILD PDF FILE REPORT AND RETURN PATH TO CALLER
    # -------------------------------------------------
    # for key, value in data.items():
    #    print(f"{key}: {value}")

    # ----4. Generate htmL template AND embed data OBJECT TO IT--------
    html = render_template("reports/pdf_report.html", **data)

    # ----5. Generate pdf file FROM HTML using weasyprint-----------------
    # base_url=current_app.root_path resolve path to css and images
    pdf = HTML(string=html, base_url=current_app.root_path).write_pdf()

    # ----6. Save pdf to static folder----------------------
    # path to .pdf file to write
    output_path = os.path.join(
        current_app.root_path, "generated_reports", "weekly_report.pdf"
    )

    with open(output_path, "wb") as f:
        f.write(pdf)

    # RETRUN PATH OF SAVED PDF
    return output_path


# ---------------
# HELPER FUNCTION FOR GENERATING PDF FILE
# --------------------
def extract_current_previous_diff(datasets: list, target_labels: list):
    """
    Extract: current (last week), previous (penultimate week) and difference from datatsets

    But only for specific label

    For example, dataset for Cpe total looks like:
    datasets: [{'label': <CpeTypeEnum.IAD: 'IAD'>, 'data': [2709, 3184, 3215, 2995, 2995]}...]

    target_labels:[CpeTypeEnum('IAD'),...]

    """
    extracted_stats = {}

    for item in datasets:
        label_name = item["label"]

        if label_name in target_labels:
            data = item["data"]
            # Ensure we have at least 2 elements to avoid errors
            if len(data) > 2:
                current = data[-1]  # Last element
                previous = data[-2]  # Penultimate element
                diff = current - previous

                extracted_stats[label_name] = {
                    "current": current,
                    "previous": previous,
                    "difference": diff,
                }

    return extracted_stats


def build_report_chart(chart_data, output_filename, title):
    """
    # build_report_char() will:
    1. build chart USING MATPLOTLIB,
    2. save it as .png
    3. and return path of saved plot image:

    """

    # Lazy Load this heavy library matplotlib
    import matplotlib

    # On servers (Linux, Docker, RunPod, etc.) you MUST force a non-GUI backend.
    # Otherwise your app will crash in headless environments.
    matplotlib.use("Agg")

    # Lazy Load this heavy library matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    labels = chart_data["labels"]
    datasets = chart_data["datasets"]

    # 1. SET THE STYLE (Modern & Minimal)
    plt.style.use("ggplot")  # Or 'seaborn-v0_8-muted' if available

    # Customize the figure colors
    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#ffffff")
    ax.set_facecolor("#f8f9fa")  # Light grey background inside chart

    # 2. DEFINE A MODERN COLOR PALETTE
    colors = ["#3498db", "#e74c3c", "#2ecc71",  "#9b59b6","#f1c40f", "#FF69B4"]

    # 3. PLOT WITH CUSTOM STYLING
    for i, dataset in enumerate(datasets):
        color = colors[i % len(colors)]
        plt.plot(
            labels,
            dataset["data"],
            label=dataset.get("label", ""),
            color=color,
            linewidth=2.5,
            marker="o",  # Adds dots to data points
            markersize=6,
            markerfacecolor="white",
            markeredgewidth=2,
            antialiased=True,
        )

    # 4. TYPOGRAPHY & LABELS
    plt.title(title, fontsize=16, fontweight="bold", pad=20, color="#2c3e50")
    plt.ylabel("Količina", fontsize=12, fontweight="semibold", color="#7f8c8d")

    # Clean up the Grid
    ax.grid(True, linestyle="--", alpha=0.6, color="#dcdde1")

    # Remove unnecessary spines (borders)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#bdc3c7")
    ax.spines["bottom"].set_color("#bdc3c7")

    # 5. LEGEND STYLING
    plt.legend(
        frameon=True,
        facecolor="white",
        edgecolor="#dcdde1",
        loc="upper left",
        fontsize=10,
        shadow=True,
    )

    # 6. TICK CUSTOMIZATION
    plt.xticks(rotation=30, ha="right", color="#7f8c8d")
    plt.yticks(color="#7f8c8d")

    plt.tight_layout()

    # SAVE
    # 2. Define path where chart image will be save
    output_path = os.path.join(
        current_app.root_path, "static/reports/charts", output_filename
    )
    plt.savefig(output_path, dpi=200, bbox_inches="tight")  # Higher DPI for crispness
    plt.close()

    # return path of saved chart image
    return f"static/reports/charts/{output_filename}"


def get_significant_changes(
    datasets,
    source,
    threshold=100,
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
