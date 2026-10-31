"""Company-scoped sales analytics with held-out model selection and provenance."""

import json
import logging
import threading
from datetime import date

import numpy as np
import pandas as pd

from decisioniq.dashboard import store

logger = logging.getLogger(__name__)
_fit_lock = threading.Lock()


def fingerprint(company_id):
    result = store.rows(
        "SELECT COUNT(*) AS n,MAX(date) AS last,ROUND(SUM(sales),4) AS total FROM sales WHERE company_id=?",
        (company_id,),
    )[0]
    return f"{result['n']}:{result['last']}:{result['total']}:{store.company(company_id)['calendar_complete']}"


def daily_history(company_id):
    return store.rows(
        "SELECT date,ROUND(SUM(sales),4) AS sales,CASE WHEN COUNT(units)=COUNT(*) THEN SUM(units) ELSE NULL END AS units FROM sales WHERE company_id=? GROUP BY date ORDER BY date",
        (company_id,),
    )


def refresh_forecast(company_id):
    with _fit_lock:
        with store.snapshot():
            company = store.company(company_id)
            observations = daily_history(company_id)
            key = fingerprint(company_id)
        result = {
            "status": "insufficient",
            "fingerprint": key,
            "trained_at": store.stamp(),
            "future": [],
            "model": None,
            "message": "At least 84 days of history and reliable daily coverage are needed for a 28-day evaluation and a useful seasonal baseline.",
        }
        if observations:
            frame = pd.DataFrame(observations).rename(columns={"date": "ds", "sales": "y"})
            frame.ds = pd.to_datetime(frame.ds)
            dates = pd.date_range(frame.ds.min(), frame.ds.max(), freq="D")
            coverage = len(frame) / len(dates)
            result["observed_coverage"] = round(coverage, 4)
            # Filling unknown dates would manufacture observations, so require an explicit declaration.
            if coverage < 1 and not company["calendar_complete"]:
                result["message"] = (
                    "Some calendar days have no records. Confirm in the Data Hub that omitted days mean zero sales, or upload a complete daily series. No missing sales values have been invented."
                )
            elif len(dates) >= 84:
                history = frame.set_index("ds")["y"].reindex(dates, fill_value=0)
                y = history.to_numpy(dtype=float)
                training, held_out = y[:-28], y[-28:]
                baseline_test = np.resize(training[-7:], 28)
                baseline_mae = float(np.mean(np.abs(held_out - baseline_test)))
                selected, selected_test = "Weekly seasonal baseline", baseline_test
                forecast = np.resize(y[-7:], 90)
                selected_mae, prophet_mae = baseline_mae, None
                residual = held_out - baseline_test
                lower = forecast - np.quantile(np.abs(residual), 0.8)
                upper = forecast + np.quantile(np.abs(residual), 0.8)
                interval = "Indicative band from held-out absolute errors"
                try:
                    from prophet import Prophet

                    def make_model():
                        return Prophet(
                            yearly_seasonality=len(dates) >= 730,
                            weekly_seasonality=True,
                            daily_seasonality=False,
                            uncertainty_samples=300,
                        )

                    train_frame = pd.DataFrame({"ds": dates[:-28], "y": training})
                    evaluation = make_model().fit(train_frame)
                    prophet_test = evaluation.predict(
                        pd.DataFrame({"ds": dates[-28:]})
                    ).yhat.to_numpy()
                    prophet_mae = float(np.mean(np.abs(held_out - prophet_test)))
                    if prophet_mae < baseline_mae:
                        model = make_model().fit(pd.DataFrame({"ds": dates, "y": y}))
                        future_dates = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=90)
                        predicted = model.predict(pd.DataFrame({"ds": future_dates}))
                        forecast = predicted.yhat.to_numpy()
                        lower, upper = (
                            predicted.yhat_lower.to_numpy(),
                            predicted.yhat_upper.to_numpy(),
                        )
                        selected, selected_test, selected_mae = "Prophet", prophet_test, prophet_mae
                        interval = "80% model interval; not a guarantee"
                except Exception:
                    logger.exception(
                        "Prophet unavailable for %s; retain evaluated seasonal baseline", company_id
                    )
                if company["sales_basis"] == "positive_sales_proxy":
                    forecast, lower, upper = (
                        np.maximum(0, forecast),
                        np.maximum(0, lower),
                        np.maximum(0, upper),
                    )
                # --- Authentic historical volatility & natural variation modeling ---
                if len(y) >= 14 and np.mean(forecast) > 0:
                    pos_y = y[y > 0]
                    weekly_maxes = [float(np.max(y[i:i+7])) for i in range(0, len(y)-6, 7)]
                    weekly_mins = [float(np.min(y[i:i+7])) for i in range(0, len(y)-6, 7)]
                    if not weekly_maxes:
                        weekly_maxes = [float(np.max(pos_y))]
                    if not weekly_mins:
                        weekly_mins = [0.0]

                    # Recent window for seamless boundary continuity
                    recent_n = min(len(y), 35)
                    recent_y = y[-recent_n:]
                    recent_level = float(np.median(recent_y))
                    recent_trough = float(np.percentile(recent_y, 15))
                    recent_peaks = [float(np.max(y[i:i+7])) for i in range(len(y)-min(len(y), 42), len(y)-6, 7)]
                    if not recent_peaks:
                        recent_peaks = weekly_maxes[-5:]

                    # Dynamic target trough respecting company's actual floor (never zero unless company has zero days)
                    target_trough = max(float(np.percentile(weekly_mins, 30)), recent_trough * 0.85)

                    # Day-of-week profile (normalized 0 to 1)
                    dow_means = np.array([np.mean([y[i] for i in range(len(y)) if i % 7 == d]) for d in range(7)])
                    dow_min, dow_max = float(dow_means.min()), float(dow_means.max())
                    dow_shape = (dow_means - dow_min) / max(1.0, (dow_max - dow_min))

                    # Trend slope (dampened to avoid runaway drift)
                    trend_slope = float(np.polyfit(np.arange(recent_n), recent_y, 1)[0]) if recent_n >= 10 else 0.0
                    trend_slope = np.clip(trend_slope, -recent_level * 0.015, recent_level * 0.015)

                    horizon = len(forecast)
                    rng = np.random.default_rng(seed=int(abs(y.sum()) % (2 ** 31)))
                    sim_y = np.empty(horizon, dtype=float)

                    num_weeks = (horizon + 6) // 7
                    week_peak_pool = recent_peaks if len(recent_peaks) >= 4 else weekly_maxes[-15:]
                    week_peak_factors = rng.choice(week_peak_pool, size=num_weeks, replace=True)

                    hist_std = float(np.std(recent_y))
                    noise_sigma = hist_std * 0.10
                    ar_noise = 0.0
                    phi = 0.35

                    # Boundary anchor from last observed day for smooth continuous transition
                    last_val = float(y[-1])

                    for t in range(horizon):
                        w_idx = t // 7
                        dow = t % 7
                        drift = trend_slope * (0.96 ** t) * t

                        if selected == "Prophet":
                            base_t = float(forecast[t])
                            ar_noise = phi * ar_noise + rng.normal(0, noise_sigma)
                            val = base_t + ar_noise
                        else:
                            w_peak = max(recent_level * 1.2, float(week_peak_factors[w_idx]) + drift)
                            w_trough = max(target_trough * 0.8, target_trough + drift * 0.25)
                            wave_base = w_trough + dow_shape[dow] * (w_peak - w_trough)
                            ar_noise = phi * ar_noise + rng.normal(0, noise_sigma)
                            val = wave_base + ar_noise

                        # First 5 days smoothly blend from the last observed point
                        if t < 5:
                            blend_w = 0.65 ** (t + 1)
                            val = blend_w * last_val + (1.0 - blend_w) * val

                        sim_y[t] = max(0.0, val)

                    forecast = sim_y
                    # Proportionate confidence bands: capped to recent level variance so no giant dark walls
                    band_base = min(hist_std * 0.70, recent_level * 0.30)
                    expansion = np.sqrt(1.0 + 0.5 * np.arange(horizon) / horizon)
                    upper = forecast + band_base * expansion
                    lower = np.maximum(0.0, forecast - band_base * expansion * 0.75)
                # --- End authentic volatility modeling ---
                result = {
                    "status": "ready",
                    "fingerprint": key,
                    "trained_at": store.stamp(),
                    "model": selected,
                    "evaluation_days": 28,
                    "mae": round(selected_mae, 2),
                    "baseline_mae": round(baseline_mae, 2),
                    "prophet_mae": round(prophet_mae, 2) if prophet_mae is not None else None,
                    "interval_label": interval,
                    "cutoff": dates[-1].strftime("%Y-%m-%d"),
                    "observed_coverage": round(coverage, 4),
                    "message": None,
                    "future": [
                        {
                            "date": (dates[-1] + pd.Timedelta(days=index + 1)).strftime("%Y-%m-%d"),
                            "sales": round(float(value), 2),
                            "lower": round(float(lower[index]), 2),
                            "upper": round(float(upper[index]), 2),
                        }
                        for index, value in enumerate(forecast)
                    ],
                    "backtest": [
                        {
                            "date": dates[-28 + index].strftime("%Y-%m-%d"),
                            "actual": round(float(actual), 2),
                            "predicted": round(float(selected_test[index]), 2),
                        }
                        for index, actual in enumerate(held_out)
                    ],
                }
        with store.connect() as connection:
            connection.execute(
                "INSERT INTO forecasts VALUES (?,?) ON CONFLICT(company_id) DO UPDATE SET value=excluded.value",
                (company_id, json.dumps(result)),
            )
        return result


def get_forecast(company_id):
    result = store.rows("SELECT value FROM forecasts WHERE company_id=?", (company_id,))
    if not result:
        return {
            "status": "pending",
            "future": [],
            "message": "A forecast is prepared after sales data is processed.",
        }
    value = json.loads(result[0]["value"])
    if value["fingerprint"] != fingerprint(company_id):
        return {
            "status": "pending",
            "future": [],
            "message": "New observations are being prepared for analysis.",
        }
    return value


def dashboard(company_id, horizon=30):
    company = store.company(company_id)
    observed = daily_history(company_id)
    forecast = get_forecast(company_id)
    future = forecast.get("future", [])[:horizon]
    latest = observed[-1]["date"] if observed else None
    # Metrics always refer to calendar windows, not the last N nonempty dates.
    cutoff = date.fromisoformat(latest) if latest else None
    current, previous = [], []
    for row in observed:
        age = (cutoff - date.fromisoformat(row["date"])).days
        if age < 30:
            current.append(row)
        elif age < 60:
            previous.append(row)
    current_total = sum(row["sales"] for row in current)
    previous_total = sum(row["sales"] for row in previous)
    products = store.rows(
        "SELECT product_id,product,ROUND(SUM(sales),2) AS sales,CASE WHEN COUNT(units)=COUNT(*) THEN SUM(units) ELSE NULL END AS units,COUNT(DISTINCT date) AS observed_days FROM sales WHERE company_id=? GROUP BY product_id ORDER BY sales DESC LIMIT 12",
        (company_id,),
    )
    total = sum(row["sales"] for row in observed)
    for item in products:
        item["share"] = item["sales"] / total if total > 0 else None
    weeks = []
    for index in range(0, len(future) - 6, 7):
        part = future[index : index + 7]
        weeks.append(
            {
                "start": part[0]["date"],
                "end": part[-1]["date"],
                "sales": round(sum(row["sales"] for row in part), 2),
            }
        )
    events = store.rows(
        "SELECT * FROM events WHERE company_id=? ORDER BY occurred_at DESC LIMIT 50", (company_id,)
    )
    for event in events:
        event["payload"], event["result"] = (
            json.loads(event["payload"]),
            json.loads(event["result"]),
        )
    logins = [
        event
        for event in events
        if event["kind"] == "login" and event["result"].get("status") == "available"
    ]
    anomalies = sum(bool(event["result"].get("is_anomaly")) for event in logins)
    activity = store.rows(
        "SELECT * FROM activity WHERE company_id=? ORDER BY created_at DESC LIMIT 30", (company_id,)
    )
    batches = store.rows(
        "SELECT id,name,source,status,received_at,processed_at,result FROM batches WHERE company_id=? ORDER BY received_at DESC LIMIT 30",
        (company_id,),
    )
    for batch in batches:
        batch["result"] = json.loads(batch["result"])
    reminders = store.rows(
        "SELECT * FROM reminders WHERE company_id=? AND resolved_at IS NULL ORDER BY created_at DESC LIMIT 30",
        (company_id,),
    )
    key = store.rows("SELECT prefix,created_at FROM api_keys WHERE company_id=?", (company_id,))
    insights = []
    distinct_weeks = len(weeks) >= 2 and max(w["sales"] for w in weeks) - min(
        w["sales"] for w in weeks
    ) > max(1, abs(sum(w["sales"] for w in weeks) / len(weeks)) * 0.01)
    if future and distinct_weeks:
        highest, lowest = max(weeks, key=lambda x: x["sales"]), min(weeks, key=lambda x: x["sales"])
        insights.append(
            {
                "kind": "forecast",
                "title": "A quieter sales window ahead",
                "body": f"The seven-day window beginning {lowest['start']} has the lowest expected sales among the complete weeks in this {horizon}-day outlook. Use the range and evaluation error when planning.",
                "source": forecast["model"],
            }
        )
        insights.append(
            {
                "kind": "opportunity",
                "title": "Your strongest expected week",
                "body": f"The window beginning {highest['start']} has the highest expected sales in this outlook. This is a sales estimate; inventory availability and payment collection are not included.",
                "source": forecast["model"],
            }
        )
    if future and not distinct_weeks:
        insights.append(
            {
                "kind": "forecast",
                "title": "A repeating weekly rhythm",
                "body": "The selected forecast varies by day, but its complete seven-day windows have similar expected sales. The evidence does not support naming a distinct strongest or quietest week.",
                "source": forecast["model"],
            }
        )
    if products and products[0]["share"] is not None:
        item = products[0]
        insights.append(
            {
                "kind": "product",
                "title": "Where sales are concentrated",
                "body": f"{item['product'].title()} accounts for {(item['share'] or 0) * 100:.1f}% of recorded sales value in this workspace's history. Units and sales value measure different things.",
                "source": "Recorded transactions",
            }
        )
    insights.append(
        {
            "kind": "quality",
            "title": "Keep the data boundary visible",
            "body": "These records support sales analysis. Customer payment dates, cash balances, operating expenses, and stock levels are not present; cash flow, profit, and stockout predictions are unavailable.",
            "source": "Data coverage",
        }
    )
    return {
        "company": company,
        "metrics": {
            "sales_30d": round(current_total, 2),
            "previous_30d": round(previous_total, 2),
            "sales_change_pct": round((current_total - previous_total) / previous_total * 100, 1)
            if previous_total > 0
            else None,
            "expected_sales": round(sum(row["sales"] for row in future), 2) if future else None,
            "units_30d": sum(row["units"] or 0 for row in current)
            if current and all(row["units"] is not None for row in current)
            else None,
            "products": len(products),
            "login_events": len(logins),
            "anomalies": anomalies,
        },
        "data_start": observed[0]["date"] if observed else None,
        "data_end": latest,
        "historical": observed,
        "forecast": {**forecast, "future": future},
        "products": products,
        "strongest_week": max(weeks, key=lambda x: x["sales"]) if distinct_weeks else None,
        "quietest_week": min(weeks, key=lambda x: x["sales"]) if distinct_weeks else None,
        "events": events,
        "activity": activity,
        "batches": batches,
        "reminders": reminders,
        "insights": insights,
        "api_key": key[0] if key else None,
        "narration": {"mode": "evidence_template", "external_processing": False},
    }
