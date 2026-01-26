import os
from flask import render_template, current_app
from app.utils.dates import get_current_week_friday
from app.services.admin import (
    get_cpe_inventory_chart_data,
    get_cpe_dismantle_chart_data,
    get_stb_inventory_chart_data,
    get_iptv_inventory_chart_data,
    get_ont_inventory_chart_data,
)


def generate_pdf():
    # Lazy Load this heavy library
    from weasyprint import HTML

    current_week_end = get_current_week_friday()

    # 1. pull data to render chart and summary tables in dictonary
    data = {
        "week": current_week_end.strftime("%d-%m-%Y"),
    }
    # ----------------------------------------------
    # COVER SECTION
    # -------------------------------------------------
    # ----------------------------------------------
    # SUMMARY SECTION
    # -------------------------------------------------

    # ----------------------------------------------
    # CHART SECTION
    # -------------------------------------------------
    # "cpe_chart_image" will be referenced in html template by img
    # build_report_char() will: build chart, save it as png and
    # return path to that saved image:
    # "cpe_chart_image": "static/reports/charts/cpe_trend.png",
    data["cpe_chart_image"] = build_report_chart(
        # get data
        chart_data_fn=get_cpe_inventory_chart_data,
        chart_kwargs={
            "city_id": None,
            "cpe_id": None,
            "cpe_type": None,
            "weeks": 10,
        },
        # save matplotlib to as image to path
        output_filename="cpe_trend.png",
        title="Trend ukupne CPE opreme u radu po svim IJ I skladištima (Zadnjih 10 sedmica)",
    )

    data["cpe_dismantle_chart_image"] = build_report_chart(
        chart_data_fn=get_cpe_dismantle_chart_data,
        chart_kwargs={
            "city_id": None,
            "cpe_id": None,
            "cpe_type": None,
            "dismantle_type_id": None,
            "weeks": 10,
        },
        output_filename="cpe_dismantle_trend.png",
        title="Trend ukupne demontirane CPE opreme po svim IJ (Zadnjih 10 sedmica)",
    )

    data["stb_chart_image"] = build_report_chart(
        chart_data_fn=get_stb_inventory_chart_data,
        chart_kwargs={
            "stb_type_id": None,
            "weeks": 10,
        },
        output_filename="stb_trend.png",
        title="Trend ukupne STB opreme u radu, IPTV platforma (Zadnjih 10 sedmica)",
    )

    data["iptv_chart_image"] = build_report_chart(
        chart_data_fn=get_iptv_inventory_chart_data,
        chart_kwargs={
            "weeks": 10,
        },
        output_filename="iptv_trend.png",
        title="Trend IPTV korisnika, IPTV platforma (Zadnjih 10 sedmica)",
    )

    data["ont_chart_image"] = build_report_chart(
        chart_data_fn=get_ont_inventory_chart_data,
        chart_kwargs={
            "city_id": None,
            "months": 5,
        },
        output_filename="ont_trend.png",
        title="Trend ukupne ONT opreme u radu po svim IJ (Zadnjih 5 mijeseci)",
    )

    # ----4. Generate htm template with embeded data--------
    html = render_template("reports/weekly_report.html", **data)

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


# * means that all parameters after the * must be passed as keyword arguments
# (with their names explicitly used) when calling the function.
# ensure clean and unambiguous function calls
def build_report_chart(*, chart_data_fn, chart_kwargs, output_filename, title):
    # 1. Get chart data. chart_data holds labels and datasets
    # (**) Used to unpack a dictionary into keyword arguments
    chart_data = chart_data_fn(**(chart_kwargs or {}))

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


def send_email():
    pass
