"""CSV ingestion with destination matching, validation, deduplication and source logging."""
from __future__ import annotations
import csv, io, re
from typing import Any
from backend.db import connect


def norm(s:str)->str:
    return re.sub(r"[^a-z0-9]+","",(s or "").lower())


def import_tourism_csv(content:bytes, filename:str, source_name:str="User-uploaded tourism dataset") -> dict[str,Any]:
    text=content.decode("utf-8-sig",errors="replace")
    reader=csv.DictReader(io.StringIO(text))
    required={"destination","year","month","visitors"}
    headers={norm(x):x for x in (reader.fieldnames or [])}
    aliases={"destination":["destination","destinationname","place","name"],"year":["year"],"month":["month"],"visitors":["visitors","visitorcount","tourists","visits"]}
    cols={}
    for field,opts in aliases.items():
        for option in opts:
            if norm(option) in headers:
                cols[field]=headers[norm(option)]; break
    if set(cols)!=required:
        raise ValueError("Tourism CSV must contain columns: destination, year, month, visitors. Optional: capacity_per_month, source, notes.")
    with connect() as conn:
        destrows=conn.execute("SELECT id,name,slug FROM destinations").fetchall()
        destmap={norm(r["name"]):r for r in destrows}; destmap.update({norm(r["slug"]):r for r in destrows})
        existing=conn.execute("SELECT id FROM data_sources WHERE name=?",(source_name,)).fetchone()
        if existing: source_id=existing["id"]
        else:
            cur=conn.execute("INSERT INTO data_sources(name,category,status,reliability,notes) VALUES(?,?,?,?,?)",(source_name,"Imported tourism statistics","Imported","User supplied; verify dataset provenance",f"Uploaded file: {filename}")); source_id=cur.lastrowid
        inserted=updated=skipped=0; errors=[]; capacity_updates=0
        for line,row in enumerate(reader,start=2):
            d=destmap.get(norm(row.get(cols["destination"],"")))
            if not d:
                skipped+=1; errors.append({"line":line,"reason":f"Unknown destination: {row.get(cols['destination'],'')}"}); continue
            try:
                year=int(row[cols["year"]]); month=int(row[cols["month"]]); visitors=float(row[cols["visitors"]])
                if not (2000<=year<=2100 and 1<=month<=12 and visitors>=0): raise ValueError("Year/month/visitors outside valid range")
            except Exception as exc:
                skipped+=1; errors.append({"line":line,"reason":str(exc)}); continue
            old=conn.execute("SELECT id FROM tourism_stats WHERE destination_id=? AND year=? AND month=?",(d["id"],year,month)).fetchone()
            conn.execute("""INSERT INTO tourism_stats(destination_id,year,month,visitors,source_id,notes) VALUES(?,?,?,?,?,?)
                ON CONFLICT(destination_id,year,month) DO UPDATE SET visitors=excluded.visitors,source_id=excluded.source_id,notes=excluded.notes,imported_at=CURRENT_TIMESTAMP""",
                (d["id"],year,month,visitors,source_id,row.get("notes","")))
            if old: updated+=1
            else: inserted+=1
            cap=row.get("capacity_per_month") or ""
            if cap:
                try:
                    c=float(cap)
                    if c>0:
                        conn.execute("UPDATE destinations SET capacity_per_month=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(c,d["id"]))
                        capacity_updates+=1
                except ValueError: errors.append({"line":line,"reason":"Invalid capacity_per_month; visitor row was imported without updating capacity."})
        conn.execute("UPDATE data_sources SET last_updated=CURRENT_TIMESTAMP,status='Imported',notes=? WHERE id=?",(f"Latest upload: {filename}. Rows inserted: {inserted}, updated: {updated}.",source_id))
        conn.commit()
    return {"inserted":inserted,"updated":updated,"skipped":skipped,"capacity_updates":capacity_updates,"errors":errors[:50],"source_id":source_id}


def import_reviews_csv(content:bytes, filename:str, source_name:str="User-uploaded review dataset") -> dict[str,Any]:
    from backend.services.sentiment import analyse_text
    reader=csv.DictReader(io.StringIO(content.decode("utf-8-sig",errors="replace")))
    headers={norm(x):x for x in (reader.fieldnames or [])}
    def choose(*names):
        for name in names:
            if norm(name) in headers: return headers[norm(name)]
        return None
    dc=choose("destination","destination_name","place"); tc=choose("review","review_text","text","comment"); rc=choose("rating","score"); ac=choose("author","name","reviewer"); datec=choose("date","review_date")
    if not dc or not tc: raise ValueError("Review CSV must contain destination and review (or review_text/text) columns. Optional: rating, author, date.")
    with connect() as conn:
        destrows=conn.execute("SELECT id,name,slug FROM destinations").fetchall(); destmap={norm(r["name"]):r for r in destrows}; destmap.update({norm(r["slug"]):r for r in destrows})
        src=conn.execute("SELECT id FROM data_sources WHERE name=?",(source_name,)).fetchone()
        if src: source_id=src["id"]
        else:
            source_id=conn.execute("INSERT INTO data_sources(name,category,status,reliability,notes) VALUES(?,?,?,?,?)",(source_name,"Reviews","Imported","User-supplied; verify license and provenance",f"Uploaded file: {filename}")).lastrowid
        inserted=skipped=0; errors=[]
        for line,row in enumerate(reader,start=2):
            d=destmap.get(norm(row.get(dc,"")))
            if not d or not row.get(tc," ").strip():
                skipped+=1; errors.append({"line":line,"reason":"Unknown destination or empty review"}); continue
            rating=None
            if rc and row.get(rc):
                try:
                    rating=float(row[rc]);
                    if not 1<=rating<=5: raise ValueError()
                except Exception:
                    skipped+=1; errors.append({"line":line,"reason":"Rating must be between 1 and 5"}); continue
            # Avoid importing the same destination/review pair repeatedly from a re-uploaded CSV.
            duplicate=conn.execute("SELECT 1 FROM reviews WHERE destination_id=? AND LOWER(TRIM(review_text))=LOWER(TRIM(?)) AND source=? LIMIT 1",
                                   (d["id"],row[tc],source_name)).fetchone()
            if duplicate:
                skipped+=1
                continue
            sentiment,aspects=analyse_text(row[tc])
            conn.execute("INSERT INTO reviews(destination_id,author,rating,review_text,source,review_date,sentiment,aspects_json) VALUES(?,?,?,?,?,?,?,?)",
                         (d["id"],(row.get(ac) if ac else "Imported reviewer") or "Imported reviewer",rating,row[tc],source_name,(row.get(datec) if datec else None) or "Imported",sentiment,__import__('json').dumps(aspects)))
            inserted+=1
        conn.execute("UPDATE data_sources SET last_updated=CURRENT_TIMESTAMP,status='Imported',notes=? WHERE id=?",(f"Latest upload: {filename}. Rows inserted: {inserted}.",source_id))
        conn.commit()
    return {"inserted":inserted,"skipped":skipped,"errors":errors[:50]}
