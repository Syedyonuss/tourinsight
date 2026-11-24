"""Baseline popularity forecasting; intentionally disabled without enough historical observations."""
from __future__ import annotations
from typing import Any
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from backend.db import connect


def _features(rows):
    values=[]
    for i,r in enumerate(rows):
        m=int(r["month"])
        values.append([i, np.sin(2*np.pi*m/12), np.cos(2*np.pi*m/12), float(r["year"])-float(rows[0]["year"])])
    return np.asarray(values,dtype=float)


def forecasts() -> dict[str, Any]:
    output=[]
    with connect() as conn:
        dests=conn.execute("SELECT id,name,slug FROM destinations WHERE active=1 ORDER BY name").fetchall()
        for d in dests:
            rows=conn.execute("SELECT year,month,visitors FROM tourism_stats WHERE destination_id=? ORDER BY year,month",(d["id"],)).fetchall()
            if len(rows)<24:
                output.append({"slug":d["slug"],"name":d["name"],"available":False,"observations":len(rows),"message":"At least 24 monthly observations (two years) are required before a baseline forecast is displayed."})
                continue
            x=_features(rows); y=np.asarray([float(r["visitors"]) for r in rows])
            split=max(18,int(len(rows)*.8)); split=min(split,len(rows)-3)
            x_train,x_test=x[:split],x[split:]; y_train,y_test=y[:split],y[split:]
            models={"Linear Regression":LinearRegression(),"Random Forest":RandomForestRegressor(n_estimators=240,max_depth=5,min_samples_leaf=2,random_state=42)}
            scores={}
            for name,model in models.items():
                model.fit(x_train,y_train); pred=model.predict(x_test)
                scores[name]={"mae":round(float(mean_absolute_error(y_test,pred)),2),"rmse":round(float(np.sqrt(mean_squared_error(y_test,pred))),2)}
            best_name=min(scores,key=lambda n:scores[n]["mae"])
            best=models[best_name]; best.fit(x,y)
            last_year=int(rows[-1]["year"]); last_month=int(rows[-1]["month"]); forecasts_list=[]
            for j in range(1,4):
                m=last_month+j; yv=last_year+(m-1)//12; mv=(m-1)%12+1
                idx=len(rows)+j-1
                xx=np.asarray([[idx,np.sin(2*np.pi*mv/12),np.cos(2*np.pi*mv/12),yv-int(rows[0]["year"])]])
                value=max(0,float(best.predict(xx)[0]))
                forecasts_list.append({"year":yv,"month":mv,"predicted_visitors":round(value)})
            output.append({"slug":d["slug"],"name":d["name"],"available":True,"observations":len(rows),"model":best_name,
                           "model_scores":scores,"history":[dict(r) for r in rows],"forecast":forecasts_list,
                           "evaluation":"Chronological holdout on the latest observations. These are baseline model estimates, not official forecasts."})
    ready=[x for x in output if x.get("available")]
    return {"destinations":output,"available_count":len(ready),"method":"Scikit-learn Linear Regression and Random Forest; selected by holdout MAE.",
            "message":None if ready else "No destination currently has at least 24 monthly tourism observations. Import official or properly licensed visitor data to activate forecasts."}
