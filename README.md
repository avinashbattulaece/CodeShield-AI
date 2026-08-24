# CodeShield AI

A Flask-based source-code plagiarism detection project.

## Features
- Individual multiple-file upload
- Entire class ZIP upload
- AST-based Python normalization
- Variable/function renaming resistance
- Structural operator comparison to reduce false positives
- High / Medium / Low risk classification
- Results page
- Student/class analytics dashboard
- Chart.js analytics
- Downloadable PDF report
- Downloadable CSV report
- SQLite analysis storage

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000/`

## ZIP format

```text
class_submissions.zip
├── student1.py
├── student2.py
├── student3.py
└── student4.py
```

Nested folders are also supported.

## Important

The application runs with:

```python
debug=False
use_reloader=False
```

This prevents Flask from restarting when uploaded ZIP files are written during analysis.
