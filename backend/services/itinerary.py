"""Practical route builder with OSRM road routing and clearly labelled fallback estimates."""
from __future__ import annotations
import math, json
from typing import Any
import httpx
from backend.db import connect
from backend.services.recommendations import generate_recommendations

CITY_COORDS={"bengaluru":(12.9716,77.5946),"bangalore":(12.9716,77.5946),"mysuru":(12.2958,76.6394),"mysore":(12.2958,76.6394),"mangaluru":(12.9141,74.8560),"mangalore":(12.9141,74.8560),"hyderabad":(17.3850,78.4867),"chennai":(13.0827,80.2707),"goa":(15.2993,74.1240),"pune":(18.5204,73.8567),"mumbai":(19.0760,72.8777),"kochi":(9.9312,76.2673),"delhi":(28.6139,77.2090),"hubballi":(15.3647,75.1240),"hubli":(15.3647,75.1240)}


def haversine(a:tuple[float,float],b:tuple[float,float])->float:
    r=6371.0; p1,p2=math.radians(a[0]),math.radians(b[0]); dp=math.radians(b[0]-a[0]); dl=math.radians(b[1]-a[1])
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(h))

async def route_geometry(points:list[tuple[float,float]]) -> dict[str,Any]:
    if len(points)<2: return {"source":"Not applicable","legs":[],"geometry":None}
    coords=";".join(f"{lon},{lat}" for lat,lon in points)
    try:
        async with httpx.AsyncClient(timeout=12.0,headers={"User-Agent":"TourInsightLocal/1.0"}) as client:
            res=await client.get(f"https://router.project-osrm.org/route/v1/driving/{coords}",params={"overview":"full","geometries":"geojson","steps":"false"})
            res.raise_for_status(); data=res.json()
        if data.get("code")=="Ok" and data.get("routes"):
            route=data["routes"][0]
            legs=[{"distance_km":round(x["distance"]/1000,1),"duration_hours":round(x["duration"]/3600,1)} for x in route.get("legs",[])]
            return {"source":"OSRM demo routing service","legs":legs,"geometry":route["geometry"]}
    except Exception:
        pass
    legs=[]
    for a,b in zip(points,points[1:]):
        dist=haversine(a,b)*1.3
        legs.append({"distance_km":round(dist,1),"duration_hours":round(dist/42,1)})
    return {"source":"Approximation only: straight-line distance × 1.3, average 42 km/h","legs":legs,"geometry":{"type":"LineString","coordinates":[[lon,lat] for lat,lon in points]}}

async def build_itinerary(payload:dict[str,Any])->dict[str,Any]:
    rec=await generate_recommendations(payload)
    options=rec["all_results"]
    if not options: raise ValueError("No destinations match the selected region.")
    # Start with the highest scored candidate then select nearby alternatives.
    selected=[options[0]]
    while len(selected)<min(int(payload["days"]),4) and len(selected)<len(options):
        last=selected[-1]
        remaining=[x for x in options if x["slug"] not in {s["slug"] for s in selected}]
        if not remaining: break
        next_dest=min(remaining,key=lambda x:haversine((last["latitude"],last["longitude"]),(x["latitude"],x["longitude"]))
                      + (100-x["score"])*0.7)
        distance=haversine((last["latitude"],last["longitude"]),(next_dest["latitude"],next_dest["longitude"]))
        if distance>320 and len(selected)>=1: break
        selected.append(next_dest)
    origin=str(payload.get("origin","Bengaluru" )).strip()
    okey=origin.lower().split(",")[0].strip()
    origin_coords=CITY_COORDS.get(okey)
    warnings=[]
    if not origin_coords:
        origin_coords=CITY_COORDS["bengaluru"]
        warnings.append("Origin was not geocoded locally; route distance starts from Bengaluru as a fallback. Add a supported city or configure a geocoding provider.")
    with connect() as conn:
        rows={r["slug"]:r for r in conn.execute("SELECT slug,budget_low,budget_high FROM destinations")}
    points=[origin_coords]+[(x["latitude"],x["longitude"]) for x in selected]
    route=await route_geometry(points)
    daily=[]
    for i,d in enumerate(selected):
        leg=route["legs"][i] if i<len(route["legs"]) else {"distance_km":0,"duration_hours":0}
        start="Travel from origin" if i==0 else f"Travel from {selected[i-1]['name']}"
        attractions=d["attractions"][:3]
        low=float(d["budget_low"]); high=float(d["budget_high"])
        daily.append({"day":i+1,"destination":d["name"],"slug":d["slug"],"travel_from":start,
                      "distance_km":leg["distance_km"],"travel_hours":leg["duration_hours"],"attractions":attractions,
                      "estimated_spend_per_person_inr":{"low":round(low),"high":round(high)},
                      "note":"One destination base per day; attraction order should be confirmed locally. Distances use the selected route source."})
    total_low=sum(x["estimated_spend_per_person_inr"]["low"] for x in daily)*int(payload.get("travellers",1))
    total_high=sum(x["estimated_spend_per_person_inr"]["high"] for x in daily)*int(payload.get("travellers",1))
    return {"title":f"{len(daily)}-day Karnataka discovery from {origin}","origin":origin,"month":payload["month"],"requested_days":payload["days"],
            "days":daily,"route":route,"total_estimate_inr":{"low":total_low,"high":total_high},"travellers":payload.get("travellers",1),
            "warnings":warnings+["Budget estimates are indicative per-person daily destination costs, not quotes; transport, permits and accommodation availability may change.",
                                  "The itinerary is a planning suggestion. Confirm opening days, permits, weather warnings and local transport before departure."],
            "recommendation_method":rec["method"]}

async def build_custom_itinerary(origin:str, month:int, travellers:int, destination_slugs:list[str]) -> dict[str,Any]:
    """Create a route from the user's explicit day-stop selections."""
    if not destination_slugs or len(destination_slugs)>14 or len(set(destination_slugs))!=len(destination_slugs):
        raise ValueError("Select between one and fourteen unique destination stops.")
    with connect() as conn:
        dests=[]
        for slug in destination_slugs:
            row=conn.execute("SELECT * FROM destinations WHERE slug=? AND active=1",(slug,)).fetchone()
            if not row: raise ValueError(f"Destination '{slug}' is unavailable.")
            from backend.db import destination_dict
            dests.append(destination_dict(row))
    key=origin.lower().split(',')[0].strip(); origin_coords=CITY_COORDS.get(key); warnings=[]
    if not origin_coords:
        origin_coords=CITY_COORDS['bengaluru']
        warnings.append("Origin was not geocoded locally; route starts from Bengaluru as a fallback.")
    points=[origin_coords]+[(d['latitude'],d['longitude']) for d in dests]
    route=await route_geometry(points)
    days=[]
    for i,d in enumerate(dests):
        leg=route['legs'][i] if i<len(route['legs']) else {'distance_km':0,'duration_hours':0}
        days.append({'day':i+1,'destination':d['name'],'slug':d['slug'],'travel_from':'Travel from origin' if i==0 else f"Travel from {dests[i-1]['name']}",
                     'distance_km':leg['distance_km'],'travel_hours':leg['duration_hours'],'attractions':d['attractions'][:3],
                     'estimated_spend_per_person_inr':{'low':round(d['budget_low']),'high':round(d['budget_high'])},
                     'note':'User-selected stop. Verify local accessibility, opening hours and travel time.'})
    low=sum(d['budget_low'] for d in dests)*travellers; high=sum(d['budget_high'] for d in dests)*travellers
    return {'title':f"{len(days)}-day editable Karnataka route from {origin}",'origin':origin,'month':month,'requested_days':len(days),'days':days,'route':route,
            'travellers':travellers,'total_estimate_inr':{'low':round(low),'high':round(high)},
            'warnings':warnings+['This route reflects your selected destinations. Budget estimates are indicative and are not live quotes.']}
