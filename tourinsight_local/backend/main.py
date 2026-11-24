"""TourInsight FastAPI application."""
from __future__ import annotations
import json, os, re, secrets, sys, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware

from backend.db import connect, init_db, destination_dict
from backend.security import hash_password, verify_password, new_reset_token, reset_token_hash
from backend.services.recommendations import generate_recommendations, INTERESTS
from backend.services.weather import live_weather
from backend.services.sentiment import dashboard_sentiment, analyse_text
from backend.services.analytics import dashboard_data
from backend.services.prediction import forecasts
from backend.services.itinerary import build_itinerary, build_custom_itinerary
from backend.services.data_quality import build_report
from backend.services.ingest import import_tourism_csv, import_reviews_csv
from backend.services.data_gov_in import connector_status, sync_tourism_resource
import httpx

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(48)
APP = FastAPI(title="TourInsight API", version="1.0.0", description="Karnataka tourism intelligence and SmartSeason recommendations")
APP.add_middleware(SessionMiddleware, secret_key=SECRET, session_cookie="tourinsight_session", max_age=60*60*24*14,
                   same_site="lax", https_only=os.getenv("COOKIE_SECURE", "false").lower()=="true")
APP.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
UPLOADS = Path(os.getenv("TOURINSIGHT_UPLOADS", str(WEB / "uploads"))).expanduser()
UPLOADS.mkdir(parents=True, exist_ok=True)
APP.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")


class RegisterBody(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)
    origin: str = Field(default="", max_length=100)
    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        v=v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",v): raise ValueError("Enter a valid email address.")
        return v

class LoginBody(BaseModel):
    email: str
    password: str

class ForgotBody(BaseModel):
    email: str

class ResetBody(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)

class ProfileBody(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    origin: str = Field(default="", max_length=100)

class RecommendationBody(BaseModel):
    origin: str = Field(min_length=2, max_length=100)
    region: str = "Any region"
    month: int = Field(ge=1, le=12)
    interests: list[str] = Field(default_factory=list, max_length=7)
    budget: float = Field(gt=0, le=10000000)
    days: int = Field(ge=1, le=14)
    travellers: int = Field(ge=1, le=12)
    group: str = "family"
    @field_validator("group")
    @classmethod
    def group_valid(cls,v):
        if v not in {"solo","family","friends","couples"}: raise ValueError("Choose solo, family, friends or couples.")
        return v
    @field_validator("interests")
    @classmethod
    def interests_valid(cls,v):
        if any(x not in INTERESTS for x in v): raise ValueError("One or more interests are not supported.")
        return list(dict.fromkeys(v))

class ReviewBody(BaseModel):
    destination_slug: str
    author: str = Field(default="Tourist", max_length=80)
    rating: float = Field(ge=1, le=5)
    review_text: str = Field(min_length=15, max_length=4000)
    image_url: str = Field(default="", max_length=500)

class ItineraryBody(RecommendationBody):
    title: Optional[str] = Field(default=None, max_length=120)

class AlternativesBody(RecommendationBody):
    target_slug: str

class CustomItineraryBody(BaseModel):
    origin: str = Field(min_length=2, max_length=100)
    month: int = Field(ge=1, le=12)
    travellers: int = Field(ge=1, le=12)
    destination_slugs: list[str] = Field(min_length=1, max_length=14)

class SavePreviewBody(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    plan: dict

class CompareBody(BaseModel):
    slugs: list[str] = Field(min_length=2, max_length=4)
    month: int = Field(ge=1, le=12)

class WeightsBody(BaseModel):
    weights: dict[str, float]

class DestinationBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    state: str = Field(default="Karnataka", min_length=2, max_length=80)
    slug: str = Field(min_length=2, max_length=100)
    district: str = ""
    region: str = ""
    category: str = "Other"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    description: str = ""
    active: bool = True
    capacity_per_month: Optional[float] = Field(default=None, gt=0)
    budget_low: float = Field(default=1500, gt=0)
    budget_high: float = Field(default=4000, gt=0)
    accessibility_score: float = Field(default=50, ge=0, le=100)
    popularity_index: float = Field(default=50, ge=0, le=100)
    image_url: str = ""


def current_user(request: Request):
    uid=request.session.get("user_id")
    if not uid: return None
    with connect() as conn:
        row=conn.execute("SELECT id,email,full_name,role,origin,created_at FROM users WHERE id=?",(uid,)).fetchone()
    if not row:
        request.session.clear(); return None
    return dict(row)


def require_user(request: Request):
    user=current_user(request)
    if not user: raise HTTPException(401,"Please log in to continue.")
    return user


def require_admin(request: Request):
    user=require_user(request)
    if user["role"]!="admin": raise HTTPException(403,"Administrator access is required.")
    return user


def public_destination(row, month: int | None=None):
    d=destination_dict(row)
    if month:
        with connect() as conn:
            s=conn.execute("SELECT score,label,basis FROM seasonal_suitability WHERE destination_id=? AND month=?",(d["id"],month)).fetchone()
            if s: d["seasonal"] = dict(s)
    with connect() as conn:
        rating=conn.execute("SELECT AVG(rating) avg,COUNT(*) n FROM reviews WHERE destination_id=? AND rating IS NOT NULL",(d["id"],)).fetchone()
        d["rating"]={"average":round(float(rating["avg"]),2),"count":rating["n"]} if rating["n"] else None
    # Do not expose internal fields that are irrelevant to the browser.
    return d


@APP.on_event("startup")
def startup():
    init_db()
    print("TourInsight database ready. Local reference catalogue: Karnataka (10 destinations).", flush=True)
    if not os.getenv("SESSION_SECRET"):
        print("NOTICE: SESSION_SECRET is temporary for this run. Set it in .env for a stable session secret.", flush=True)


@APP.middleware("http")
async def security_headers(request: Request, call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


@APP.get("/")
def home():
    return FileResponse(WEB/"index.html")

@APP.get("/api/health")
def health():
    with connect() as conn:
        n=conn.execute("SELECT COUNT(*) n FROM destinations WHERE active=1").fetchone()["n"]
    return {"status":"ok","application":"TourInsight","database":"SQLite","active_destinations":n,"time":datetime.now(timezone.utc).isoformat()}

@APP.get("/api/weights")
def public_weights():
    with connect() as conn: rows=conn.execute("SELECT key,value,label FROM recommendation_weights ORDER BY rowid").fetchall()
    return {"weights":[dict(r) for r in rows]}

@APP.get("/api/meta")
def meta():
    with connect() as conn:
        regions=[r[0] for r in conn.execute("SELECT DISTINCT region FROM destinations WHERE active=1 ORDER BY region") if r[0]]
        categories=[r[0] for r in conn.execute("SELECT DISTINCT category FROM destinations WHERE active=1 ORDER BY category") if r[0]]
    return {"regions":["Any region"]+regions,"categories":categories,"interests":INTERESTS,
            "months":["January","February","March","April","May","June","July","August","September","October","November","December"],
            "state":"Karnataka","scope_note":"The initial reference catalogue is Karnataka. The database includes a state field for expansion across India."}

@APP.get("/api/auth/me")
def auth_me(request:Request):
    return {"user":current_user(request)}

@APP.post("/api/auth/register")
def register(body:RegisterBody,request:Request):
    try: ph=hash_password(body.password)
    except ValueError as exc: raise HTTPException(400,str(exc))
    with connect() as conn:
        try:
            cur=conn.execute("INSERT INTO users(email,full_name,password_hash,origin) VALUES(?,?,?,?)",(body.email,body.full_name.strip(),ph,body.origin.strip()))
            uid=cur.lastrowid; conn.commit()
        except Exception as exc:
            if "UNIQUE" in str(exc).upper(): raise HTTPException(409,"An account with this email already exists.")
            raise
    request.session.clear(); request.session["user_id"]=uid
    return {"message":"Account created successfully.","user":current_user(request)}

@APP.post("/api/auth/login")
def login(body:LoginBody,request:Request):
    email=body.email.strip().lower()
    with connect() as conn:
        row=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not row or not verify_password(body.password,row["password_hash"]):
            raise HTTPException(401,"Email or password is incorrect.")
        conn.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?",(row["id"],)); conn.commit()
    request.session.clear(); request.session["user_id"]=row["id"]
    return {"message":"Logged in successfully.","user":current_user(request)}

@APP.post("/api/auth/logout")
def logout(request:Request):
    request.session.clear(); return {"message":"Logged out."}

@APP.post("/api/auth/profile")
def update_profile(body:ProfileBody,request:Request):
    user=require_user(request)
    with connect() as conn:
        conn.execute("UPDATE users SET full_name=?,origin=? WHERE id=?",(body.full_name.strip(),body.origin.strip(),user["id"])); conn.commit()
    return {"user":current_user(request)}

@APP.post("/api/auth/forgot-password")
def forgot_password(body:ForgotBody,request:Request):
    email=body.email.strip().lower()
    with connect() as conn:
        user=conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        if user:
            token,token_hash=new_reset_token(); expires=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
            conn.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)",(user["id"],token_hash,expires)); conn.commit()
            reset_url=str(request.base_url).rstrip("/")+"/?reset="+token
            print("[TourInsight local password reset] "+reset_url,flush=True)
    return {"message":"If that email is registered, a password reset link has been generated. In local mode, check the server terminal."}

@APP.post("/api/auth/reset-password")
def reset_password(body:ResetBody,request:Request):
    try: ph=hash_password(body.new_password)
    except ValueError as exc: raise HTTPException(400,str(exc))
    token_hash=reset_token_hash(body.token)
    with connect() as conn:
        row=conn.execute("SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL",(token_hash,)).fetchone()
        if not row: raise HTTPException(400,"This reset link is invalid or has already been used.")
        expiry=datetime.fromisoformat(row["expires_at"].replace("Z","+00:00"))
        if expiry < datetime.now(timezone.utc): raise HTTPException(400,"This reset link has expired. Request a new one.")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",(ph,row["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=?",(row["id"],)); conn.commit()
    request.session.clear(); request.session["user_id"]=row["user_id"]
    return {"message":"Password updated successfully.","user":current_user(request)}

@APP.get("/api/destinations")
def list_destinations(q:str="",region:str="",category:str="",sort:str="name",month:int|None=None):
    sql="SELECT * FROM destinations WHERE active=1"; params=[]
    if q:
        sql+=" AND (name LIKE ? OR district LIKE ? OR description LIKE ?)"; term=f"%{q}%"; params += [term,term,term]
    if region and region!="Any region": sql+=" AND (region=? OR district=?)"; params += [region,region]
    if category and category!="All categories": sql+=" AND category=?"; params.append(category)
    order="name COLLATE NOCASE" if sort=="name" else "popularity_index DESC" if sort=="popularity" else "budget_low ASC" if sort=="budget" else "accessibility_score DESC"
    sql+=" ORDER BY "+order
    with connect() as conn: rows=conn.execute(sql,params).fetchall()
    return {"destinations":[public_destination(r,month) for r in rows],"count":len(rows),"baseline_note":"Popularity is an editorial discoverability index, not an official visitor count. Budget and access scores are indicative."}

@APP.get("/api/destinations/{slug}")
def destination_detail(slug:str):
    with connect() as conn:
        row=conn.execute("SELECT * FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone()
        if not row: raise HTTPException(404,"Destination not found.")
        d=destination_dict(row)
        seasonal=conn.execute("SELECT month,score,label,basis FROM seasonal_suitability WHERE destination_id=? ORDER BY month",(d["id"],)).fetchall()
        reviews=conn.execute("SELECT author,rating,review_text,review_date,source FROM reviews WHERE destination_id=? ORDER BY review_date DESC LIMIT 30",(d["id"],)).fetchall()
    return {"destination":d,"seasonal":[dict(x) for x in seasonal],"reviews":[dict(x) for x in reviews]}

@APP.post("/api/destinations/compare")
def compare_destinations(body:CompareBody):
    with connect() as conn:
        output=[]
        for slug in body.slugs:
            row=conn.execute("SELECT * FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone()
            if not row: continue
            d=destination_dict(row)
            s=conn.execute("SELECT score,label FROM seasonal_suitability WHERE destination_id=? AND month=?",(d["id"],body.month)).fetchone()
            r=conn.execute("SELECT AVG(rating) avg,COUNT(*) n FROM reviews WHERE destination_id=? AND rating IS NOT NULL",(d["id"],)).fetchone()
            d["seasonal_score"]=s["score"] if s else None; d["seasonal_label"]=s["label"] if s else None
            d["rating"]={"average":round(float(r["avg"]),2),"count":r["n"]} if r["n"] else None
            output.append(d)
    return {"destinations":output,"note":"Scores and costs include editorial planning baselines. Ratings only appear when stored reviews exist."}

@APP.post("/api/recommendations")
async def recommendations(body:RecommendationBody,request:Request):
    payload=body.model_dump()
    result=await generate_recommendations(payload)
    user=current_user(request)
    if user:
        with connect() as conn:
            conn.execute("INSERT INTO recommendation_history(user_id,input_json,results_json) VALUES(?,?,?)",(user["id"],json.dumps(payload),json.dumps(result["results"]))); conn.commit()
    return result

@APP.post("/api/alternatives")
async def alternatives(body:AlternativesBody):
    payload=body.model_dump(); target=payload.pop("target_slug")
    rec=await generate_recommendations(payload)
    with connect() as conn:
        target_row=conn.execute("SELECT * FROM destinations WHERE slug=?",(target,)).fetchone()
    if not target_row: raise HTTPException(404,"Destination not found.")
    target_d=destination_dict(target_row); target_interests=set(target_d["interests"])
    candidates=[]
    target_scored=next((x for x in rec["all_results"] if x["slug"]==target),None)
    for d in rec["all_results"]:
        if d["slug"]==target: continue
        overlap=len(target_interests.intersection(set(d["interests"])))
        reasons=[]
        if overlap: reasons.append(f"Shares {overlap} travel-interest category/categories with {target_d['name']}")
        if target_scored and d["season_score"]>target_scored["season_score"]+8: reasons.append("has a stronger seasonal fit for your selected month")
        if target_scored and d["score_breakdown"].get("budget",0)>target_scored["score_breakdown"].get("budget",0)+8: reasons.append("fits your budget more comfortably")
        if target_scored and d["score"]>target_scored["score"]+5: reasons.append("has a higher overall SmartSeason score")
        if not reasons: reasons.append("offers another suitable experience under the same travel preferences")
        d["alternative_reason"]="; ".join(reasons).capitalize()+"."
        candidates.append(d)
    candidates.sort(key=lambda x:(len(target_interests.intersection(set(x["interests"]))),x["score"]),reverse=True)
    return {"target":target_d["name"],"alternatives":candidates[:4],"note":"Alternatives are ranked using shared interest categories and the same explainable SmartSeason scoring model."}

@APP.get("/api/weather/{slug}")
async def weather(slug:str):
    with connect() as conn: row=conn.execute("SELECT * FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone()
    if not row: raise HTTPException(404,"Destination not found.")
    data=await live_weather(destination_dict(row))
    return {"destination":row["name"],**data}

@APP.get("/api/analytics/tourism-series")
def tourism_series(destination:str="all",year:int|None=None):
    sql="SELECT s.year,s.month,SUM(s.visitors) visitors FROM tourism_stats s JOIN destinations d ON d.id=s.destination_id WHERE 1=1"
    params=[]
    if destination!="all": sql+=" AND d.slug=?"; params.append(destination)
    if year is not None: sql+=" AND s.year=?"; params.append(year)
    sql+=" GROUP BY s.year,s.month ORDER BY s.year,s.month"
    with connect() as conn: rows=conn.execute(sql,params).fetchall()
    return {"rows":[dict(r) for r in rows],"scope":"All destinations" if destination=="all" else destination}

@APP.get("/api/dashboard")
def dashboard(): return dashboard_data()

@APP.get("/api/sentiment")
def sentiment(): return dashboard_sentiment()

@APP.post("/api/reviews")
def create_review(body:ReviewBody,request:Request):
    user=current_user(request); sentiment_label,aspects=analyse_text(body.review_text)
    with connect() as conn:
        dest=conn.execute("SELECT id,name FROM destinations WHERE slug=? AND active=1",(body.destination_slug,)).fetchone()
        if not dest: raise HTTPException(404,"Destination not found.")
        conn.execute("INSERT INTO reviews(destination_id,user_id,author,rating,review_text,source,sentiment,aspects_json,image_url) VALUES(?,?,?,?,?,'User-submitted feedback',?,?,?)",
                     (dest["id"],user["id"] if user else None,body.author.strip() or "Tourist",body.rating,body.review_text,sentiment_label,json.dumps(aspects),body.image_url or None))
        conn.commit()
    return {"message":"Thank you. Your feedback has been saved.","sentiment":sentiment_label,"aspects":aspects,"destination":dest["name"]}

@APP.get("/api/predictions")
def prediction_data(): return forecasts()

@APP.get("/api/quality")
def quality_public():
    report=build_report()
    # Public view suppresses row-level inspection detail.
    return {"generated_at":report["generated_at"],"summary":report["summary"],"notes":report["notes"]}

@APP.post("/api/itineraries/preview")
async def itinerary_preview(body:ItineraryBody):
    try: return await build_itinerary(body.model_dump())
    except ValueError as exc: raise HTTPException(400,str(exc))

@APP.post("/api/itineraries/custom-preview")
async def custom_itinerary_preview(body:CustomItineraryBody):
    try: return await build_custom_itinerary(body.origin,body.month,body.travellers,body.destination_slugs)
    except ValueError as exc: raise HTTPException(400,str(exc))

@APP.post("/api/itineraries/save-preview")
def save_preview(body:SavePreviewBody,request:Request):
    user=require_user(request)
    plan=body.plan
    if not isinstance(plan.get("days"),list) or not plan["days"] or len(plan["days"])>14: raise HTTPException(400,"The itinerary preview is invalid.")
    slugs=[str(x.get("slug","")) for x in plan["days"]]
    with connect() as conn:
        placeholders=','.join('?' for _ in slugs)
        valid=conn.execute(f"SELECT slug FROM destinations WHERE active=1 AND slug IN ({placeholders})",slugs).fetchall()
        if len(valid)!=len(set(slugs)): raise HTTPException(400,"The plan contains an unavailable destination.")
        cur=conn.execute("INSERT INTO itineraries(user_id,title,origin,month,days,plan_json) VALUES(?,?,?,?,?,?)",
            (user["id"],body.title.strip(),str(plan.get("origin","")),int(plan.get("month",1)),len(plan["days"]),json.dumps(plan)))
        conn.commit()
    return {"id":cur.lastrowid,"message":"Edited itinerary saved to your account."}

@APP.post("/api/itineraries")
async def save_itinerary(body:ItineraryBody,request:Request):
    user=require_user(request)
    try: plan=await build_itinerary(body.model_dump())
    except ValueError as exc: raise HTTPException(400,str(exc))
    title=(body.title or plan["title"]).strip()
    with connect() as conn:
        cur=conn.execute("INSERT INTO itineraries(user_id,title,origin,month,days,plan_json) VALUES(?,?,?,?,?,?)",
                         (user["id"],title,body.origin,body.month,body.days,json.dumps(plan)))
        conn.commit(); iid=cur.lastrowid
    return {"id":iid,"title":title,"plan":plan,"message":"Itinerary saved to your account."}

@APP.get("/api/itineraries")
def my_itineraries(request:Request):
    user=require_user(request)
    with connect() as conn: rows=conn.execute("SELECT id,title,origin,month,days,created_at,plan_json FROM itineraries WHERE user_id=? ORDER BY created_at DESC",(user["id"],)).fetchall()
    return {"itineraries":[{"id":r["id"],"title":r["title"],"origin":r["origin"],"month":r["month"],"days":r["days"],"created_at":r["created_at"],"plan":json.loads(r["plan_json"])} for r in rows]}

@APP.get("/api/itineraries/{itinerary_id}")
def get_itinerary(itinerary_id:int,request:Request):
    user=require_user(request)
    with connect() as conn: row=conn.execute("SELECT id,title,origin,month,days,created_at,plan_json FROM itineraries WHERE id=? AND user_id=?",(itinerary_id,user["id"])).fetchone()
    if not row: raise HTTPException(404,"Itinerary not found.")
    return {"id":row["id"],"title":row["title"],"origin":row["origin"],"month":row["month"],"days":row["days"],"created_at":row["created_at"],"plan":json.loads(row["plan_json"])}

@APP.delete("/api/itineraries/{itinerary_id}")
def delete_itinerary(itinerary_id:int,request:Request):
    user=require_user(request)
    with connect() as conn:
        cur=conn.execute("DELETE FROM itineraries WHERE id=? AND user_id=?",(itinerary_id,user["id"]))
        if cur.rowcount==0: raise HTTPException(404,"Itinerary not found.")
        conn.commit()
    return {"message":"Itinerary deleted."}

@APP.get("/api/sources")
def sources():
    with connect() as conn: rows=conn.execute("SELECT name,category,url,status,attribution,reliability,last_updated,notes FROM data_sources ORDER BY category,name").fetchall()
    return {"sources":[dict(r) for r in rows]}

# ---------- administrator API ----------
@APP.get("/api/admin/overview")
def admin_overview(request:Request):
    require_admin(request)
    return {"dashboard":dashboard_data(),"quality":build_report()}

@APP.get("/api/admin/users")
def admin_users(request:Request):
    require_admin(request)
    with connect() as conn: rows=conn.execute("SELECT id,email,full_name,role,origin,created_at,last_login FROM users ORDER BY created_at DESC").fetchall()
    return {"users":[dict(r) for r in rows]}

@APP.patch("/api/admin/users/{user_id}/role")
def admin_role(user_id:int,role:str,request:Request):
    admin=require_admin(request)
    if role not in ("tourist","admin"): raise HTTPException(400,"Role must be tourist or admin.")
    if user_id==admin["id"] and role!="admin": raise HTTPException(400,"You cannot remove your own administrator role.")
    with connect() as conn:
        cur=conn.execute("UPDATE users SET role=? WHERE id=?",(role,user_id))
        if not cur.rowcount: raise HTTPException(404,"User not found.")
        conn.commit()
    return {"message":"User role updated."}

@APP.get("/api/admin/destinations")
def admin_destinations(request:Request):
    require_admin(request)
    with connect() as conn: rows=conn.execute("SELECT * FROM destinations ORDER BY state,name").fetchall()
    return {"destinations":[destination_dict(r) for r in rows]}

@APP.patch("/api/admin/destinations/{slug}")
def update_destination(slug:str,body:dict,request:Request):
    require_admin(request)
    allowed={"capacity_per_month","active","budget_low","budget_high","accessibility_score","popularity_index","description","district","region","category","image_url"}
    values={k:v for k,v in body.items() if k in allowed}
    if not values: raise HTTPException(400,"No supported destination fields supplied.")
    if "capacity_per_month" in values and values["capacity_per_month"] is not None and float(values["capacity_per_month"])<=0: raise HTTPException(400,"Capacity must be positive.")
    for field in ("accessibility_score","popularity_index"):
        if field in values and not 0<=float(values[field])<=100: raise HTTPException(400,f"{field} must be between 0 and 100.")
    sql="UPDATE destinations SET "+", ".join(f"{k}=?" for k in values)+",updated_at=CURRENT_TIMESTAMP WHERE slug=?"
    with connect() as conn:
        cur=conn.execute(sql,[*values.values(),slug])
        if not cur.rowcount: raise HTTPException(404,"Destination not found.")
        conn.commit()
    return {"message":"Destination updated."}

@APP.post("/api/admin/destinations")
def add_destination(body:DestinationBody,request:Request):
    require_admin(request)
    slug=re.sub(r"[^a-z0-9-]+","-",body.slug.lower()).strip("-")
    with connect() as conn:
        try:
            cur=conn.execute("""INSERT INTO destinations(slug,name,state,district,region,latitude,longitude,category,description,capacity_per_month,budget_low,budget_high,accessibility_score,popularity_index,image_url,active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug,body.name,body.state,body.district,body.region,body.latitude,body.longitude,body.category,body.description,body.capacity_per_month,body.budget_low,body.budget_high,body.accessibility_score,body.popularity_index,body.image_url,int(body.active)))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper(): raise HTTPException(409,"That destination slug already exists.")
            raise
        did=cur.lastrowid
        for m in range(1,13): conn.execute("INSERT INTO seasonal_suitability(destination_id,month,score,label) VALUES(?,?,50,'Needs seasonal curation')",(did,m))
        conn.commit()
    return {"message":"Destination created. Add verified seasonal guidance before using it in live recommendations.","slug":slug}

@APP.get("/api/admin/weights")
def get_weights(request:Request):
    require_admin(request)
    with connect() as conn: rows=conn.execute("SELECT key,value,label FROM recommendation_weights ORDER BY rowid").fetchall()
    return {"weights":[dict(r) for r in rows]}

@APP.put("/api/admin/weights")
def set_weights(body:WeightsBody,request:Request):
    require_admin(request)
    required={"seasonal","weather","interest","popularity","budget","accessibility"}
    if set(body.weights)!=required: raise HTTPException(400,"Provide all six recommendation weight keys.")
    if any(v<0 or v>100 for v in body.weights.values()): raise HTTPException(400,"Weights must be between 0 and 100.")
    if abs(sum(body.weights.values())-100)>0.01: raise HTTPException(400,"Recommendation weights must sum to 100%.")
    with connect() as conn:
        for k,v in body.weights.items(): conn.execute("UPDATE recommendation_weights SET value=? WHERE key=?",(v,k))
        conn.commit()
    return {"message":"Recommendation weights updated."}

@APP.get("/api/admin/quality")
def admin_quality(request:Request):
    admin=require_admin(request); report=build_report()
    with connect() as conn:
        conn.execute("INSERT INTO data_quality_reports(report_json,generated_by) VALUES(?,?)",(json.dumps(report),admin["id"])); conn.commit()
    return report

@APP.post("/api/admin/import/tourism-stats")
async def admin_import_stats(request:Request,file:UploadFile=File(...),source_name:str=Form("User-uploaded tourism dataset")):
    require_admin(request)
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a CSV file.")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,"CSV must be smaller than 10 MB.")
    try: return import_tourism_csv(content,file.filename,source_name)
    except ValueError as exc: raise HTTPException(400,str(exc))

@APP.post("/api/admin/import/reviews")
async def admin_import_reviews(request:Request,file:UploadFile=File(...),source_name:str=Form("User-uploaded review dataset")):
    require_admin(request)
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a CSV file.")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,"CSV must be smaller than 10 MB.")
    try: return import_reviews_csv(content,file.filename,source_name)
    except ValueError as exc: raise HTTPException(400,str(exc))

@APP.get("/api/admin/connectors/data-gov-in/status")
def data_gov_in_status(request:Request):
    require_admin(request)
    return connector_status()

@APP.post("/api/admin/connectors/data-gov-in/sync")
async def data_gov_in_sync(request:Request):
    require_admin(request)
    try:
        return await sync_tourism_resource()
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except httpx.HTTPStatusError as exc:
        status=exc.response.status_code
        raise HTTPException(502,f"data.gov.in returned HTTP {status}. Check the resource ID, API key and resource access.")
    except httpx.HTTPError as exc:
        raise HTTPException(502,f"Could not reach data.gov.in: {str(exc)[:180]}")

@APP.get("/api/admin/sources")
def admin_sources(request:Request):
    require_admin(request)
    with connect() as conn: rows=conn.execute("SELECT * FROM data_sources ORDER BY category,name").fetchall()
    return {"sources":[dict(r) for r in rows]}

@APP.post("/api/admin/sources")
def add_source(body:dict,request:Request):
    require_admin(request)
    name=str(body.get("name","")).strip(); category=str(body.get("category","Other")).strip()
    if len(name)<2: raise HTTPException(400,"Source name is required.")
    with connect() as conn:
        try:
            cur=conn.execute("INSERT INTO data_sources(name,category,url,status,attribution,reliability,notes) VALUES(?,?,?,?,?,?,?)",
                (name,category,body.get("url"),body.get("status","Manual import required"),body.get("attribution"),body.get("reliability"),body.get("notes")))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper(): raise HTTPException(409,"Source already exists.")
            raise
        conn.commit()
    return {"id":cur.lastrowid,"message":"Data source added."}

@APP.get("/api/admin/activity")
def admin_activity(request:Request):
    require_admin(request)
    with connect() as conn:
        users=conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        logged=conn.execute("SELECT COUNT(*) n FROM users WHERE last_login IS NOT NULL").fetchone()["n"]
        recs=conn.execute("SELECT COUNT(*) n FROM recommendation_history").fetchone()["n"]
        trips=conn.execute("SELECT COUNT(*) n FROM itineraries").fetchone()["n"]
    return {"users":users,"users_logged_in":logged,"recommendation_runs":recs,"saved_itineraries":trips}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:APP", host=os.getenv("HOST","127.0.0.1"), port=int(os.getenv("PORT","8501")), reload=False)


# Community, journals, collaborative trips, public sharing and destination check-ins.
@APP.get("/api/community/posts")
def community_posts(destination: str = ""):
    sql = """SELECT p.id,p.title,p.body,p.image_url,p.post_type,p.created_at,u.full_name author,
             d.name destination,d.slug destination_slug FROM community_posts p
             JOIN users u ON u.id=p.user_id LEFT JOIN destinations d ON d.slug=p.destination_slug"""
    params=[]
    if destination:
        sql += " WHERE p.destination_slug=?"; params.append(destination)
    sql += " ORDER BY p.created_at DESC LIMIT 60"
    with connect() as conn: rows=conn.execute(sql,params).fetchall()
    return {"posts":[dict(r) for r in rows]}

@APP.post("/api/community/posts")
def create_community_post(body: dict, request: Request):
    user=require_user(request)
    title=str(body.get("title","")).strip()[:120]
    text=str(body.get("body","")).strip()[:5000]
    slug=str(body.get("destination_slug","")).strip() or None
    image_url=str(body.get("image_url","")).strip()[:500] or None
    post_type=str(body.get("post_type","story"))
    if len(title)<3 or len(text)<10: raise HTTPException(400,"Add a title and at least 10 characters of story.")
    if post_type not in {"story","tip","question","photo"}: post_type="story"
    with connect() as conn:
        if slug and not conn.execute("SELECT 1 FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone(): raise HTTPException(404,"Destination not found.")
        cur=conn.execute("INSERT INTO community_posts(user_id,destination_slug,title,body,image_url,post_type) VALUES(?,?,?,?,?,?)",(user["id"],slug,title,text,image_url,post_type)); conn.commit()
    return {"id":cur.lastrowid,"message":"Your travel story is now published to the local community."}

@APP.post("/api/community/upload")
async def community_upload(request: Request, file: UploadFile = File(...)):
    require_user(request)
    allowed={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}
    if file.content_type not in allowed: raise HTTPException(400,"Upload a JPG, PNG or WEBP image.")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(413,"Image must be 5 MB or smaller.")
    signatures={"image/jpeg":content.startswith(b"\xff\xd8\xff"),"image/png":content.startswith(b"\x89PNG\r\n\x1a\n"),"image/webp":len(content)>12 and content[:4]==b"RIFF" and content[8:12]==b"WEBP"}
    if not signatures.get(file.content_type,False): raise HTTPException(400,"The uploaded file does not match its image format.")
    name=uuid.uuid4().hex+allowed[file.content_type]
    (UPLOADS/name).write_bytes(content)
    return {"url":"/uploads/"+name,"filename":name}

@APP.get("/api/journal")
def list_journal(request: Request):
    user=require_user(request)
    with connect() as conn:
        rows=conn.execute("""SELECT j.*,d.name destination FROM travel_journal j LEFT JOIN destinations d ON d.slug=j.destination_slug
                            WHERE j.user_id=? ORDER BY COALESCE(j.visit_date,j.created_at) DESC""",(user["id"],)).fetchall()
    return {"entries":[dict(r) for r in rows]}

@APP.post("/api/journal")
def add_journal(body: dict, request: Request):
    user=require_user(request)
    title=str(body.get("title","")).strip()[:120]; notes=str(body.get("notes","")).strip()[:5000]
    slug=str(body.get("destination_slug","")).strip() or None
    visit_date=str(body.get("visit_date","")).strip()[:10] or None
    image_url=str(body.get("image_url","")).strip()[:500] or None
    if len(title)<2 or len(notes)<5: raise HTTPException(400,"Add a title and a few notes for your journal entry.")
    with connect() as conn:
        if slug and not conn.execute("SELECT 1 FROM destinations WHERE slug=?",(slug,)).fetchone(): raise HTTPException(404,"Destination not found.")
        cur=conn.execute("INSERT INTO travel_journal(user_id,destination_slug,title,visit_date,notes,image_url) VALUES(?,?,?,?,?,?)",(user["id"],slug,title,visit_date,notes,image_url)); conn.commit()
    return {"id":cur.lastrowid,"message":"Journal entry saved."}

@APP.delete("/api/journal/{entry_id}")
def delete_journal(entry_id: int, request: Request):
    user=require_user(request)
    with connect() as conn:
        cur=conn.execute("DELETE FROM travel_journal WHERE id=? AND user_id=?",(entry_id,user["id"])); conn.commit()
    if not cur.rowcount: raise HTTPException(404,"Journal entry not found.")
    return {"message":"Journal entry deleted."}

@APP.get("/api/groups")
def list_groups(request: Request):
    user=require_user(request)
    with connect() as conn:
        rows=conn.execute("""SELECT g.id,g.name,g.invite_code,g.created_at,g.owner_id,g.itinerary_id,
            (SELECT COUNT(*) FROM trip_group_members m WHERE m.group_id=g.id) member_count,
            u.full_name owner_name FROM trip_groups g JOIN trip_group_members mine ON mine.group_id=g.id
            JOIN users u ON u.id=g.owner_id WHERE mine.user_id=? ORDER BY g.created_at DESC""",(user["id"],)).fetchall()
    return {"groups":[dict(r) for r in rows]}

@APP.post("/api/groups")
def create_group(body: dict, request: Request):
    user=require_user(request)
    name=str(body.get("name","")).strip()[:100]
    itinerary_id=body.get("itinerary_id")
    if len(name)<3: raise HTTPException(400,"Give your trip group a name.")
    with connect() as conn:
        if itinerary_id is not None and not conn.execute("SELECT 1 FROM itineraries WHERE id=? AND user_id=?",(itinerary_id,user["id"])).fetchone(): raise HTTPException(404,"Saved itinerary not found.")
        code=secrets.token_urlsafe(7).replace("-","").replace("_","")[:9].upper()
        cur=conn.execute("INSERT INTO trip_groups(owner_id,itinerary_id,name,invite_code) VALUES(?,?,?,?)",(user["id"],itinerary_id,name,code))
        conn.execute("INSERT INTO trip_group_members(group_id,user_id) VALUES(?,?)",(cur.lastrowid,user["id"])); conn.commit()
    return {"id":cur.lastrowid,"invite_code":code,"message":"Trip group created. Share the invite code with your travellers."}

@APP.post("/api/groups/join")
def join_group(body: dict, request: Request):
    user=require_user(request); code=str(body.get("invite_code","")).strip().upper()
    with connect() as conn:
        group=conn.execute("SELECT id FROM trip_groups WHERE invite_code=?",(code,)).fetchone()
        if not group: raise HTTPException(404,"That invite code was not found.")
        conn.execute("INSERT OR IGNORE INTO trip_group_members(group_id,user_id) VALUES(?,?)",(group["id"],user["id"])); conn.commit()
    return {"message":"You joined the trip group."}

def require_group_member(conn, group_id: int, user_id: int):
    if not conn.execute("SELECT 1 FROM trip_group_members WHERE group_id=? AND user_id=?",(group_id,user_id)).fetchone():
        raise HTTPException(403,"You must join this trip group to access its planning board.")

@APP.get("/api/groups/{group_id}/suggestions")
def group_suggestions(group_id: int, request: Request):
    user=require_user(request)
    with connect() as conn:
        require_group_member(conn,group_id,user["id"])
        rows=conn.execute("""SELECT s.id,s.destination_slug,d.name destination,s.note,s.created_at,u.full_name author,
            COUNT(v.user_id) votes,MAX(CASE WHEN v.user_id=? THEN 1 ELSE 0 END) voted
            FROM trip_group_suggestions s JOIN destinations d ON d.slug=s.destination_slug JOIN users u ON u.id=s.user_id
            LEFT JOIN trip_group_votes v ON v.suggestion_id=s.id WHERE s.group_id=?
            GROUP BY s.id ORDER BY votes DESC,s.created_at DESC""",(user["id"],group_id)).fetchall()
    return {"suggestions":[dict(r) for r in rows]}

@APP.post("/api/groups/{group_id}/suggestions")
def add_group_suggestion(group_id: int, body: dict, request: Request):
    user=require_user(request); slug=str(body.get("destination_slug","")).strip(); note=str(body.get("note","")).strip()[:500]
    with connect() as conn:
        require_group_member(conn,group_id,user["id"])
        if not conn.execute("SELECT 1 FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone(): raise HTTPException(404,"Destination not found.")
        cur=conn.execute("INSERT INTO trip_group_suggestions(group_id,user_id,destination_slug,note) VALUES(?,?,?,?)",(group_id,user["id"],slug,note)); conn.commit()
    return {"id":cur.lastrowid,"message":"Destination suggestion added to the group board."}

@APP.post("/api/groups/{group_id}/suggestions/{suggestion_id}/vote")
def vote_group_suggestion(group_id: int, suggestion_id: int, request: Request):
    user=require_user(request)
    with connect() as conn:
        require_group_member(conn,group_id,user["id"])
        if not conn.execute("SELECT 1 FROM trip_group_suggestions WHERE id=? AND group_id=?",(suggestion_id,group_id)).fetchone(): raise HTTPException(404,"Suggestion not found.")
        existing=conn.execute("SELECT 1 FROM trip_group_votes WHERE suggestion_id=? AND user_id=?",(suggestion_id,user["id"])).fetchone()
        if existing: conn.execute("DELETE FROM trip_group_votes WHERE suggestion_id=? AND user_id=?",(suggestion_id,user["id"])); voted=False
        else: conn.execute("INSERT INTO trip_group_votes(suggestion_id,user_id) VALUES(?,?)",(suggestion_id,user["id"])); voted=True
        conn.commit()
    return {"voted":voted,"message":"Your vote was updated."}

@APP.post("/api/itineraries/{itinerary_id}/share")
def share_itinerary(itinerary_id: int, request: Request):
    user=require_user(request)
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM itineraries WHERE id=? AND user_id=?",(itinerary_id,user["id"])).fetchone(): raise HTTPException(404,"Saved itinerary not found.")
        row=conn.execute("SELECT share_token FROM shared_itineraries WHERE itinerary_id=? AND owner_id=?",(itinerary_id,user["id"])).fetchone()
        token=row["share_token"] if row else secrets.token_urlsafe(24)
        if not row: conn.execute("INSERT INTO shared_itineraries(itinerary_id,owner_id,share_token) VALUES(?,?,?)",(itinerary_id,user["id"],token)); conn.commit()
    return {"url":str(request.base_url).rstrip("/")+"/shared/"+token}

@APP.get("/shared/{token}", response_class=HTMLResponse)
def public_shared_itinerary(token: str):
    from html import escape
    with connect() as conn:
        row=conn.execute("SELECT i.title,i.origin,i.month,i.days,i.plan_json,u.full_name owner FROM shared_itineraries s JOIN itineraries i ON i.id=s.itinerary_id JOIN users u ON u.id=s.owner_id WHERE s.share_token=?",(token,)).fetchone()
    if not row: raise HTTPException(404,"Shared itinerary not found.")
    plan=json.loads(row["plan_json"])
    month_names=["January","February","March","April","May","June","July","August","September","October","November","December"]
    days_html="".join(
        "<article class='day'><span>DAY " + str(int(d.get('day',i+1))).zfill(2) + "</span><h2>" + escape(str(d.get('destination','Stop'))) + "</h2><p>" + escape(str(d.get('travel_from',''))) + " · " + escape(str(d.get('distance_km','—'))) + " km · " + escape(str(d.get('travel_hours','—'))) + " hr</p><p>" + escape(' · '.join(map(str,d.get('attractions',[])))) + "</p></article>"
        for i,d in enumerate(plan.get("days",[]))
    )
    title=escape(str(row['title'])); owner=escape(str(row['owner'])); origin=escape(str(row['origin']))
    month=month_names[max(0,min(11,int(row['month'])-1))]
    html="""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"""+title+" · TourInsight"+"""</title><style>*{box-sizing:border-box}body{margin:0;background:#f7f4e9;color:#202923;font:16px/1.6 Arial,sans-serif;background-image:radial-gradient(#d8d5c7 .7px,transparent .7px);background-size:15px 15px}main{max-width:980px;margin:0 auto;padding:42px 22px}.brand{font-weight:900;letter-spacing:-2px;font-size:22px}.hero,.day{border:3px solid #202923;box-shadow:6px 6px 0 #263329;border-radius:10px;padding:24px;background:#fffdf5;margin:20px 0}.hero{background:#c5d9bd}h1{font-size:clamp(34px,7vw,62px);line-height:1.02;letter-spacing:-3px;margin:12px 0}h1 em{color:#6d4d3b;font-style:normal}.day{display:inline-block;vertical-align:top;width:calc(50% - 16px);margin-right:12px;min-height:180px}.day span{font-size:11px;font-weight:900;letter-spacing:2px;color:#557a5d}.day h2{margin:6px 0}.note{font-size:12px;color:#596657}@media(max-width:650px){.day{width:100%;margin-right:0}}</style><main><div class='brand'>Tour<span style='color:#557a5d'>Insight</span> ✳</div><section class='hero'><div style='font-size:11px;font-weight:900;letter-spacing:2px'>A SHARED TRAVEL PLAN · KARNATAKA</div><h1>"""+title+"""<br><em>let's go places.</em></h1><p>Shared by """+owner+" · From "+origin+" · "+month+" · "+str(int(row['days']))+" days</p><p class='note'>This is a read-only shared itinerary. Confirm transport, opening hours, permits and prices independently before travel.</p></section><h2>The route</h2>"""+days_html+"""<p class='note'>Made with TourInsight · Tourism discovery and trip planning for Karnataka.</p></main></html>"""
    return HTMLResponse(html)

@APP.post("/api/checkins")
def add_checkin(body: dict, request: Request):
    user=require_user(request); slug=str(body.get("destination_slug","")).strip(); visited=str(body.get("visited_on",datetime.now().date().isoformat()))[:10]; note=str(body.get("note","")).strip()[:500]
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone(): raise HTTPException(404,"Destination not found.")
        conn.execute("INSERT OR IGNORE INTO destination_checkins(user_id,destination_slug,visited_on,note) VALUES(?,?,?,?)",(user["id"],slug,visited,note)); conn.commit()
        rows=conn.execute("SELECT DISTINCT destination_slug FROM destination_checkins WHERE user_id=?",(user["id"],)).fetchall()
    return {"visited_count":len(rows),"message":"Visit added to your travel passport."}

@APP.get("/api/challenges")
def challenges(request: Request):
    user=require_user(request)
    with connect() as conn:
        visited=conn.execute("SELECT COUNT(DISTINCT destination_slug) n FROM destination_checkins WHERE user_id=?",(user["id"],)).fetchone()["n"]
        rows=conn.execute("SELECT destination_slug,visited_on,note FROM destination_checkins WHERE user_id=? ORDER BY visited_on DESC",(user["id"],)).fetchall()
    goals=[{"id":"first-step","name":"First footprints","description":"Visit your first Karnataka destination.","target":1,"progress":min(visited,1)},
           {"id":"weekender","name":"Weekend wanderer","description":"Explore three different destinations.","target":3,"progress":min(visited,3)},
           {"id":"state-explorer","name":"State explorer","description":"Check in at six destinations.","target":6,"progress":min(visited,6)},
           {"id":"ten-stop","name":"Ten-stop trailblazer","description":"Visit all ten starter catalogue destinations.","target":10,"progress":min(visited,10)}]
    return {"visited_count":visited,"checkins":[dict(r) for r in rows],"challenges":goals}

@APP.get("/api/transport/{slug}")
def transport_info(slug: str):
    with connect() as conn: d=conn.execute("SELECT name,district,latitude,longitude FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone()
    if not d: raise HTTPException(404,"Destination not found.")
    q=str(d["name"])+" Karnataka"
    from urllib.parse import quote
    return {"destination":dict(d),"links":[
      {"mode":"Bus","provider":"KSRTC","url":"https://ksrtc.in/"},
      {"mode":"Train","provider":"IRCTC","url":"https://www.irctc.co.in/"},
      {"mode":"Flight","provider":"Air India","url":"https://www.airindia.com/"},
      {"mode":"Map & directions","provider":"OpenStreetMap","url":"https://www.openstreetmap.org/search?query="+quote(q)}],
      "note":"These links open official provider or map websites. Live schedules, fares and seat availability are not queried by TourInsight."}

@APP.get("/api/emergency")
def emergency_info():
    return {"contacts":[{"name":"India Emergency Response Support System","number":"112","detail":"Pan-India emergency number for police, fire and medical assistance","url":"https://112.gov.in/"}],
            "note":"For immediate danger, call 112. Confirm local hospital, police station and park/forest control-room details with official local sources before travel."}
