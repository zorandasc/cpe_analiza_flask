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
        
    """

    body_html = """
           
    """
  
    # SEND EMAIL TO RECIPIENTS
    result = send_email(
        pdf_path=pdf_path,
        recipients=recipients,
        subject="Sedmični izvještaj o CPE inventaru",
        body_text=body_text,
        body_html=body_html,
    )

    settings.last_sent_at = datetime.now()
    db.session.commit()

    return "Sent"