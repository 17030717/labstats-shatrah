
import os
import csv
import io
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key-before-production")

database_url = os.getenv("DATABASE_URL", "sqlite:///labstats.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

DEPARTMENTS = [
    ("الكيمياء السريرية", "K"),
    ("أمراض الدم", "H"),
    ("المناعة", "I"),
    ("المناعة والهرمونات", "R"),
    ("الأحياء المجهرية", "M"),
    ("الطفيليات", "P"),
    ("الفحص قبل الزواج", "B"),
    ("الطوارئ المختبرية", "E"),
]

SHIFTS = [
    "صباحي",
    "الشفت الوسطي الأول",
    "الشفت الوسطي الثاني",
    "الشفت الخافر الأول",
    "الشفت الخافر الثاني",
    "الشفت الخافر الثالث",
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    shift = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    active = db.Column(db.Boolean, nullable=False, default=True)

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.String(10), nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False, index=True)
    shift = db.Column(db.String(100), nullable=False, index=True)
    user_code = db.Column(db.String(20), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    reviewers = db.Column(db.Integer, nullable=False, default=0)
    tests = db.Column(db.Integer, nullable=False, default=0)
    rejected = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

def seed_users():
    if User.query.count() > 0:
        return
    db.session.add(User(code="A99999", department="الإدارة", shift="مدير النظام", role="admin"))
    seq = 1
    for department, letter in DEPARTMENTS:
        for shift in SHIFTS:
            db.session.add(User(
                code=f"{letter}{seq:05d}",
                department=department,
                shift=shift,
                role="user"
            ))
            seq += 1
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_users()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session or session["user"]["role"] != "admin":
            flash("هذه الصفحة مخصصة للمدير فقط.", "danger")
            return redirect(url_for("home"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        user = User.query.filter_by(code=code, active=True).first()
        if not user:
            flash("رمز الدخول غير صحيح.", "danger")
        else:
            session["user"] = {
                "code": user.code,
                "department": user.department,
                "shift": user.shift,
                "role": user.role,
            }
            return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/home")
@login_required
def home():
    user = session["user"]
    today = date.today().isoformat()
    query = Entry.query.filter_by(entry_date=today)
    if user["role"] != "admin":
        query = query.filter_by(department=user["department"])
    entries = query.all()
    sums = {
        "reviewers": sum(e.reviewers for e in entries),
        "tests": sum(e.tests for e in entries),
        "rejected": sum(e.rejected for e in entries),
    }
    last = Entry.query.order_by(Entry.id.desc()).first()
    return render_template("home.html", sums=sums, last=last, today=today)

@app.route("/entry", methods=["GET", "POST"])
@login_required
def entry():
    user = session["user"]
    if request.method == "POST":
        try:
            entry_date = datetime.strptime(request.form["entry_date"], "%Y-%m-%d").date().isoformat()
            reviewers = int(request.form.get("reviewers", 0))
            tests = int(request.form.get("tests", 0))
            rejected = int(request.form.get("rejected", 0))
            if min(reviewers, tests, rejected) < 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("تحقق من التاريخ والأعداد.", "danger")
            return redirect(url_for("entry"))

        sender = request.form.get("sender_name", "").strip()
        if not sender:
            flash("أدخل اسم المرسل.", "danger")
            return redirect(url_for("entry"))

        department = user["department"] if user["role"] != "admin" else request.form.get("department", "").strip()
        shift = user["shift"] if user["role"] != "admin" else request.form.get("shift", "").strip()
        if not department or not shift:
            flash("أدخل القسم والشفت.", "danger")
            return redirect(url_for("entry"))

        db.session.add(Entry(
            entry_date=entry_date,
            department=department,
            shift=shift,
            user_code=user["code"],
            sender_name=sender,
            reviewers=reviewers,
            tests=tests,
            rejected=rejected,
            notes=request.form.get("notes", "").strip(),
        ))
        db.session.commit()
        flash("تم حفظ الإحصائية بنجاح.", "success")
        return redirect(url_for("home"))

    return render_template(
        "entry.html",
        departments=[d[0] for d in DEPARTMENTS],
        shifts=SHIFTS,
        today=date.today().isoformat(),
    )

def get_report_rows(mode, value):
    user = session["user"]
    query = Entry.query

    if mode == "daily":
        query = query.filter(Entry.entry_date == value)
    elif mode == "monthly":
        query = query.filter(Entry.entry_date.like(f"{value}%"))
    else:
        query = query.filter(Entry.entry_date.like(f"{value}%"))

    if user["role"] != "admin":
        query = query.filter(Entry.department == user["department"])

    entries = query.all()
    grouped = {}
    for e in entries:
        row = grouped.setdefault(e.department, {"department": e.department, "reviewers": 0, "tests": 0, "rejected": 0})
        row["reviewers"] += e.reviewers
        row["tests"] += e.tests
        row["rejected"] += e.rejected
    return sorted(grouped.values(), key=lambda x: x["department"])

@app.route("/report/<mode>")
@login_required
def report(mode):
    if mode not in ("daily", "monthly", "yearly"):
        return redirect(url_for("home"))
    defaults = {
        "daily": date.today().isoformat(),
        "monthly": date.today().strftime("%Y-%m"),
        "yearly": date.today().strftime("%Y"),
    }
    value = request.args.get("value", defaults[mode])
    rows = get_report_rows(mode, value)
    totals = {
        "reviewers": sum(r["reviewers"] for r in rows),
        "tests": sum(r["tests"] for r in rows),
        "rejected": sum(r["rejected"] for r in rows),
    }
    return render_template("report.html", mode=mode, value=value, rows=rows, totals=totals)

@app.route("/export/<mode>")
@login_required
def export(mode):
    value = request.args.get("value", "")
    rows = get_report_rows(mode, value)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["القسم", "عدد المراجعين", "عدد الفحوصات", "العينات المرفوضة", "فحوصات لكل مراجع"])
    for r in rows:
        ratio = round(r["tests"] / r["reviewers"], 2) if r["reviewers"] else 0
        writer.writerow([r["department"], r["reviewers"], r["tests"], r["rejected"], ratio])
    stream = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    stream.seek(0)
    return send_file(stream, mimetype="text/csv", as_attachment=True, download_name=f"lab_report_{mode}_{value}.csv")

@app.route("/dashboard")
@admin_required
def dashboard():
    day = request.args.get("day", date.today().isoformat())
    users = User.query.filter_by(role="user", active=True).order_by(User.department, User.id).all()
    status = []
    for user in users:
        entries = Entry.query.filter_by(entry_date=day, department=user.department, shift=user.shift).all()
        status.append({
            "department": user.department,
            "shift": user.shift,
            "sent": bool(entries),
            "reviewers": sum(e.reviewers for e in entries),
            "tests": sum(e.tests for e in entries),
        })
    return render_template("dashboard.html", day=day, status=status)

@app.route("/users")
@admin_required
def users():
    rows = User.query.order_by(User.role.desc(), User.id).all()
    return render_template("users.html", rows=rows)

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
