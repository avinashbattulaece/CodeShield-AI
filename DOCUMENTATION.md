# CodeShield AI - Project Documentation

## 1. Objective
CodeShield AI detects potentially plagiarized source code across multiple student submissions.

## 2. Workflow
1. User uploads multiple source files or a ZIP.
2. Files are stored outside the static/template folders.
3. ZIP submissions are safely extracted.
4. Every pair of submissions is compared.
5. Python code is parsed using AST normalization.
6. Variable and function names are normalized.
7. Operators and program structure are preserved.
8. Raw, normalized and structural similarity are combined.
9. Results are classified as High, Medium or Low Risk.
10. Results are stored in SQLite and can be exported as PDF or CSV.

## 3. False-positive reduction
The detector does not rely only on text similarity. It preserves important AST operators such as Add, Mult, Div and Compare. Therefore, addition and multiplication programs with similar formatting should receive a substantially lower structural score.

## 4. Technologies
- Python
- Flask
- SQLite
- Python AST
- difflib
- Chart.js
- ReportLab

## 5. Limitations
This is an academic prototype and should be used as a screening system. High-risk results should still be manually reviewed.
