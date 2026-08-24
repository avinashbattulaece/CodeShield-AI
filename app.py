import os
import io
import csv
import uuid
import zipfile
import sqlite3
from pathlib import Path
from itertools import combinations
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from utils.plagiarism_detector import analyze_pair

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "instance" / "uploads"
EXTRACT_DIR = BASE_DIR / "instance" / "extracted"
REPORT_DIR = BASE_DIR / "instance" / "reports"
DB_PATH = BASE_DIR / "codeshield.db"

for folder in (UPLOAD_DIR, EXTRACT_DIR, REPORT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "codeshield-ai-final-project"
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {".py", ".java", ".c", ".cpp", ".cc", ".h", ".hpp", ".js", ".ts"}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            threshold INTEGER,
            total_files INTEGER,
            total_comparisons INTEGER,
            high_count INTEGER,
            medium_count INTEGER,
            low_count INTEGER,
            results_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def allowed(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def status_for(score, threshold):
    medium_threshold = max(1, threshold - 20)
    if score >= threshold:
        return "HIGH RISK"
    if score >= medium_threshold:
        return "MEDIUM RISK"
    return "LOW RISK"

def safe_read(path):
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except Exception:
            pass
    return ""

def extract_zip(zip_path, destination):
    extracted = []
    destination = destination.resolve()

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(destination)):
                continue

            if target.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, open(target, "wb") as dst:
                shutil_copyfileobj(src, dst)
            extracted.append(target)

    return extracted

def shutil_copyfileobj(src, dst, length=1024 * 1024):
    while True:
        data = src.read(length)
        if not data:
            break
        dst.write(data)

def save_analysis(analysis_id, threshold, files_count, results):
    import json
    high = sum(r["status"] == "HIGH RISK" for r in results)
    medium = sum(r["status"] == "MEDIUM RISK" for r in results)
    low = sum(r["status"] == "LOW RISK" for r in results)

    conn = db()
    conn.execute("""
        INSERT INTO analyses
        (id, created_at, threshold, total_files, total_comparisons,
         high_count, medium_count, low_count, results_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        analysis_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        threshold,
        files_count,
        len(results),
        high, medium, low,
        json.dumps(results)
    ))
    conn.commit()
    conn.close()

def load_analysis(analysis_id):
    import json
    conn = db()
    row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    data = dict(row)
    data["results"] = json.loads(data.pop("results_json"))
    return data

def build_pdf(analysis):
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("CodeShield AI", styles["Title"]))
    story.append(Paragraph("Intelligent Source Code Plagiarism Detection Report", styles["Heading2"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated: {analysis['created_at']}", styles["BodyText"]))
    story.append(Paragraph(f"Files analyzed: {analysis['total_files']}", styles["BodyText"]))
    story.append(Paragraph(f"Similarity threshold: {analysis['threshold']}%", styles["BodyText"]))
    story.append(Spacer(1, 12))

    summary = [
        ["Total Comparisons", "High Risk", "Medium Risk", "Low Risk"],
        [
            str(analysis["total_comparisons"]),
            str(analysis["high_count"]),
            str(analysis["medium_count"]),
            str(analysis["low_count"]),
        ],
    ]
    table = Table(summary, colWidths=[125, 100, 110, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b9c2cc")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 18))

    rows = [["Student 1", "Student 2", "Similarity", "Status"]]
    for result in analysis["results"]:
        rows.append([
            result["file1"],
            result["file2"],
            f"{result['similarity']:.2f}%",
            result["status"],
        ])

    result_table = Table(rows, repeatRows=1, colWidths=[125, 125, 90, 110])
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(result_table)
    doc.build(story)
    output.seek(0)
    return output

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    threshold = request.form.get("threshold", "60")
    try:
        threshold = min(100, max(1, int(threshold)))
    except ValueError:
        threshold = 60

    analysis_id = uuid.uuid4().hex
    work_dir = UPLOAD_DIR / analysis_id
    extract_dir = EXTRACT_DIR / analysis_id
    work_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    source_files = []

    for uploaded in request.files.getlist("files"):
        if uploaded and uploaded.filename and allowed(uploaded.filename):
            name = f"{uuid.uuid4().hex}_{Path(uploaded.filename).name}"
            target = work_dir / name
            uploaded.save(target)
            source_files.append(target)

    class_zip = request.files.get("class_zip")
    if class_zip and class_zip.filename:
        if not class_zip.filename.lower().endswith(".zip"):
            flash("Class upload must be a ZIP file.", "error")
            return redirect(url_for("index"))

        zip_path = work_dir / f"{uuid.uuid4().hex}.zip"
        class_zip.save(zip_path)

        try:
            source_files.extend(extract_zip(zip_path, extract_dir))
        except zipfile.BadZipFile:
            flash("The uploaded ZIP file is invalid or corrupted.", "error")
            return redirect(url_for("index"))

    if len(source_files) < 2:
        flash("Upload at least two supported source-code files, or a ZIP containing at least two files.", "error")
        return redirect(url_for("index"))

    submissions = []
    used_names = set()
    for path in source_files:
        name = path.name
        if "_" in name and path.parent == work_dir:
            name = name.split("_", 1)[1]
        if name in used_names:
            name = f"{path.parent.name}_{name}"
        used_names.add(name)
        submissions.append({"name": name, "code": safe_read(path)})

    results = []
    for first, second in combinations(submissions, 2):
        comparison = analyze_pair(first["code"], second["code"])
        similarity = comparison["similarity"]
        status = status_for(similarity, threshold)

        results.append({
            "file1": first["name"],
            "file2": second["name"],
            "similarity": similarity,
            "status": status,
            "code1": comparison["code1"],
            "code2": comparison["code2"],
            "matched_blocks": comparison["matched_blocks"],
            "explanation": comparison["explanation"],
        })

    results.sort(key=lambda item: item["similarity"], reverse=True)

    save_analysis(analysis_id, threshold, len(submissions), results)
    session["analysis_id"] = analysis_id
    return redirect(url_for("results", analysis_id=analysis_id))

@app.route("/results/<analysis_id>")
def results(analysis_id):
    analysis = load_analysis(analysis_id)
    if analysis is None:
        flash("Analysis not found.", "error")
        return redirect(url_for("index"))
    return render_template("results.html", analysis=analysis)

@app.route("/dashboard/<analysis_id>")
def dashboard(analysis_id):
    analysis = load_analysis(analysis_id)
    if analysis is None:
        flash("Analysis not found.", "error")
        return redirect(url_for("index"))

    students = {}
    for result in analysis["results"]:
        for key in ("file1", "file2"):
            students.setdefault(result[key], {"comparisons": 0, "high": 0, "medium": 0, "low": 0})
            students[result[key]]["comparisons"] += 1
            if result["status"] == "HIGH RISK":
                students[result[key]]["high"] += 1
            elif result["status"] == "MEDIUM RISK":
                students[result[key]]["medium"] += 1
            else:
                students[result[key]]["low"] += 1

    return render_template("dashboard.html", analysis=analysis, students=students)

@app.route("/report/<analysis_id>.pdf")
def report_pdf(analysis_id):
    analysis = load_analysis(analysis_id)
    if analysis is None:
        return "Analysis not found", 404

    pdf = build_pdf(analysis)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"CodeShield_Report_{analysis_id[:8]}.pdf"
    )

@app.route("/report/<analysis_id>.csv")
def report_csv(analysis_id):
    analysis = load_analysis(analysis_id)
    if analysis is None:
        return "Analysis not found", 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student 1", "Student 2", "Similarity", "Status"])
    for result in analysis["results"]:
        writer.writerow([
            result["file1"],
            result["file2"],
            f"{result['similarity']:.2f}",
            result["status"],
        ])

    data = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"CodeShield_Report_{analysis_id[:8]}.csv"
    )

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
