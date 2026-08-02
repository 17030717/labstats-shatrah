
import os
from datetime import date, datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "temporary-secret")
db_url = os.getenv("DATABASE_URL", "sqlite:///labstats.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

DEPARTMENTS=[("الكيمياء السريرية","K"),("أمراض الدم","H"),("المناعة","I"),("المناعة والهرمونات","R"),("الأحياء المجهرية","M"),("الطفيليات","P"),("الفحص قبل الزواج","B"),("الطوارئ المختبرية","E")]
SHIFTS=["صباحي","الشفت الوسطي الأول","الشفت الوسطي الثاني","الشفت الخافر الأول","الشفت الخافر الثاني","الشفت الخافر الثالث"]

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(20),unique=True,nullable=False)
    department=db.Column(db.String(100),nullable=False)
    shift=db.Column(db.String(100),nullable=False)
    role=db.Column(db.String(20),nullable=False,default="user")
    active=db.Column(db.Boolean,nullable=False,default=True)

class Entry(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    entry_date=db.Column(db.String(10),nullable=False)
    department=db.Column(db.String(100),nullable=False)
    shift=db.Column(db.String(100),nullable=False)
    sender_name=db.Column(db.String(100),nullable=False)
    reviewers=db.Column(db.Integer,nullable=False,default=0)
    tests=db.Column(db.Integer,nullable=False,default=0)
    rejected=db.Column(db.Integer,nullable=False,default=0)
    notes=db.Column(db.Text)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)

with app.app_context():
    db.create_all()
    if User.query.count()==0:
        db.session.add(User(code="A99999",department="الإدارة",shift="مدير النظام",role="admin"))
        n=1
        for dep,letter in DEPARTMENTS:
            for shift in SHIFTS:
                db.session.add(User(code=f"{letter}{n:05d}",department=dep,shift=shift))
                n+=1
        db.session.commit()

STYLE="<style>body{margin:0;font-family:Arial,Tahoma;background:#f4f7fb;direction:rtl;color:#1f2937}header{background:#17365d;color:white;padding:18px;text-align:center;font-size:20px;font-weight:bold}main{max-width:1000px;margin:auto;padding:20px}.card{background:white;max-width:520px;margin:40px auto;padding:25px;border-radius:14px;box-shadow:0 4px 18px #0001}input,select,textarea{width:100%;padding:12px;margin:7px 0 14px;border:1px solid #cbd5e1;border-radius:9px;box-sizing:border-box;font-size:16px}button,a.btn{display:inline-block;background:#2f75b5;color:white;padding:12px 18px;border:0;border-radius:9px;text-decoration:none;font-size:16px;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}.menu{padding:25px;text-align:center;color:white;text-decoration:none;border-radius:12px;font-size:19px;font-weight:bold}.blue{background:#2f75b5}.green{background:#70ad47}.purple{background:#8064a2}.orange{background:#c55a11}.gray{background:#7f8c8d}.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.kpi{background:white;padding:20px;border-radius:12px;text-align:center}.kpi b{font-size:28px;color:#17365d}table{width:100%;border-collapse:collapse;background:white}th,td{padding:11px;border-bottom:1px solid #ddd;text-align:center}th{background:#17365d;color:white}.ok{color:#166534;font-weight:bold}.no{color:#991b1b;font-weight:bold}.alert{padding:10px;border-radius:8px;background:#fee2e2;margin:10px 0}@media(max-width:700px){.grid,.kpis{grid-template-columns:1fr}table{font-size:13px}}</style>"

def page(title,body):
    alerts="".join(f'<div class="alert">{m}</div>' for m in get_flashed_messages())
    logout=f'<p><a href="{url_for("logout")}">تسجيل الخروج</a></p>' if "user" in session else ""
    html=f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{STYLE}</head><body><header>نظام إدارة وإحصائيات مختبر مستشفى الشطرة العام</header><main>{logout}{alerts}{body}</main></body></html>'
    return render_template_string(html)

def login_required(fn):
    @wraps(fn)
    def inner(*a,**k):
        if "user" not in session:return redirect(url_for("login"))
        return fn(*a,**k)
    return inner

def admin_required(fn):
    @wraps(fn)
    def inner(*a,**k):
        if session.get("user",{}).get("role")!="admin":return redirect(url_for("home"))
        return fn(*a,**k)
    return inner

@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        code=request.form.get("code","").strip().upper()
        u=User.query.filter_by(code=code,active=True).first()
        if u:
            session["user"]={"code":u.code,"department":u.department,"shift":u.shift,"role":u.role}
            return redirect(url_for("home"))
        flash("رمز الدخول غير صحيح")
    body="""<div class="card"><h2>تسجيل الدخول</h2><form method="post"><label>رمز الدخول</label><input name="code" required autofocus><button>دخول</button></form><p>رمز المدير الافتراضي: A99999</p></div>"""
    return page("تسجيل الدخول",body)

@app.route("/logout")
def logout():
    session.clear();return redirect(url_for("login"))

@app.route("/home")
@login_required
def home():
    u=session["user"];today=date.today().isoformat()
    q=Entry.query.filter_by(entry_date=today)
    if u["role"]!="admin":q=q.filter_by(department=u["department"])
    es=q.all();r=sum(x.reviewers for x in es);t=sum(x.tests for x in es);j=sum(x.rejected for x in es)
    admin=""
    if u["role"]=="admin":
        admin=f'<a class="menu orange" href="{url_for("dashboard")}">لوحة المدير</a><a class="menu gray" href="{url_for("users")}">المستخدمون والرموز</a>'
    body=f'<h2>الواجهة الرئيسية</h2><div class="kpis"><div class="kpi">المراجعون<br><b>{r}</b></div><div class="kpi">الفحوصات<br><b>{t}</b></div><div class="kpi">المرفوضة<br><b>{j}</b></div></div><div class="grid" style="margin-top:20px"><a class="menu blue" href="{url_for("entry")}">إدخال الإحصائية</a><a class="menu green" href="{url_for("report",mode="daily")}">التقرير اليومي</a><a class="menu purple" href="{url_for("report",mode="monthly")}">التقرير الشهري</a><a class="menu purple" href="{url_for("report",mode="yearly")}">التقرير السنوي</a>{admin}</div>'
    return page("الرئيسية",body)

@app.route("/entry",methods=["GET","POST"])
@login_required
def entry():
    u=session["user"]
    if request.method=="POST":
        try:
            reviewers=int(request.form.get("reviewers",0));tests=int(request.form.get("tests",0));rejected=int(request.form.get("rejected",0))
            d=datetime.strptime(request.form["entry_date"],"%Y-%m-%d").date().isoformat()
        except Exception:
            flash("تحقق من الأعداد والتاريخ");return redirect(url_for("entry"))
        dep=u["department"] if u["role"]!="admin" else request.form.get("department")
        shift=u["shift"] if u["role"]!="admin" else request.form.get("shift")
        sender=request.form.get("sender_name","").strip()
        if not sender or not dep or not shift:
            flash("أكمل جميع الحقول");return redirect(url_for("entry"))
        db.session.add(Entry(entry_date=d,department=dep,shift=shift,sender_name=sender,reviewers=reviewers,tests=tests,rejected=rejected,notes=request.form.get("notes","")))
        db.session.commit();return redirect(url_for("home"))
    if u["role"]=="admin":
        deps="".join(f"<option>{x[0]}</option>" for x in DEPARTMENTS);shifts="".join(f"<option>{x}</option>" for x in SHIFTS)
        extra=f'<label>القسم</label><select name="department">{deps}</select><label>الشفت</label><select name="shift">{shifts}</select>'
    else:
        extra=f'<p><b>القسم:</b> {u["department"]}</p><p><b>الشفت:</b> {u["shift"]}</p>'
    body=f'<div class="card"><h2>إدخال الإحصائية</h2><form method="post"><label>التاريخ</label><input type="date" name="entry_date" value="{date.today().isoformat()}" required>{extra}<label>اسم المرسل</label><input name="sender_name" required><label>عدد المراجعين</label><input type="number" min="0" name="reviewers" value="0"><label>عدد الفحوصات</label><input type="number" min="0" name="tests" value="0"><label>العينات المرفوضة</label><input type="number" min="0" name="rejected" value="0"><label>ملاحظات</label><textarea name="notes"></textarea><button>حفظ وإرسال</button></form></div>'
    return page("إدخال الإحصائية",body)

def report_data(mode,value):
    u=session["user"];q=Entry.query
    q=q.filter(Entry.entry_date==value) if mode=="daily" else q.filter(Entry.entry_date.like(value+"%"))
    if u["role"]!="admin":q=q.filter(Entry.department==u["department"])
    g={}
    for e in q.all():
        row=g.setdefault(e.department,[0,0,0]);row[0]+=e.reviewers;row[1]+=e.tests;row[2]+=e.rejected
    return g

@app.route("/report/<mode>")
@login_required
def report(mode):
    defaults={"daily":date.today().isoformat(),"monthly":date.today().strftime("%Y-%m"),"yearly":date.today().strftime("%Y")}
    value=request.args.get("value",defaults.get(mode,date.today().isoformat()));data=report_data(mode,value)
    rows="".join(f"<tr><td>{dep}</td><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>" for dep,v in data.items()) or '<tr><td colspan="4">لا توجد بيانات</td></tr>'
    typ={"daily":"date","monthly":"month","yearly":"number"}.get(mode,"date")
    body=f'<h2>التقرير</h2><form><input type="{typ}" name="value" value="{value}"><button>عرض</button></form><table><tr><th>القسم</th><th>المراجعون</th><th>الفحوصات</th><th>المرفوضة</th></tr>{rows}</table>'
    return page("التقرير",body)

@app.route("/dashboard")
@admin_required
def dashboard():
    day=request.args.get("day",date.today().isoformat());rows=[]
    for u in User.query.filter_by(role="user",active=True).all():
        es=Entry.query.filter_by(entry_date=day,department=u.department,shift=u.shift).all()
        status='<span class="ok">تم الإرسال</span>' if es else '<span class="no">لم يرسل</span>'
        rows.append(f"<tr><td>{u.department}</td><td>{u.shift}</td><td>{status}</td><td>{sum(e.reviewers for e in es)}</td><td>{sum(e.tests for e in es)}</td></tr>")
    body=f'<h2>لوحة المدير</h2><form><input type="date" name="day" value="{day}"><button>تحديث</button></form><table><tr><th>القسم</th><th>الشفت</th><th>الحالة</th><th>المراجعون</th><th>الفحوصات</th></tr>{"".join(rows)}</table>'
    return page("لوحة المدير",body)

@app.route("/users")
@admin_required
def users():
    rows="".join(f"<tr><td>{u.code}</td><td>{u.department}</td><td>{u.shift}</td></tr>" for u in User.query.all())
    return page("المستخدمون",f'<h2>المستخدمون والرموز</h2><table><tr><th>الرمز</th><th>القسم</th><th>الشفت</th></tr>{rows}</table>')

@app.route("/health")
def health():return {"status":"ok"}

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
