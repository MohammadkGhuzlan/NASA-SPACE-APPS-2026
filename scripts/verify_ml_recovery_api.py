"""Rollback-isolated, real-data five-location API checks. No fake source values.

Run after the historical operational checks. These are plumbing/refusal checks,
not an independent accuracy benchmark and not account-authentication tests.
"""
import argparse
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import engine, get_db
from backend.main import app
from backend.models import EnvironmentalLocation
from backend.machine_learning.common import read_json, write_json, now
from backend.machine_learning.operational_checks import LOCATIONS


def run(operational_path, out):
    source = read_json(operational_path)
    results = {}
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: session
        try:
            with TestClient(app) as client, TestClient(app) as other:
                status = client.get("/api/analysis/model-status").json()
                assert not status["predictionsEnabled"], "This refusal check must not run against an activated model"
                for name, (lat, lon) in LOCATIONS.items():
                    historical = source["locations"][name]["prepared"]
                    assert historical["selected_coordinates"] == {"latitude": lat, "longitude": lon}
                    # The 2019–2025 dashboard is deliberately a separate cache.
                    location = session.scalar(select(EnvironmentalLocation).where(
                        EnvironmentalLocation.latitude == lat, EnvironmentalLocation.longitude == lon))
                    assert location is not None, f"Dashboard data absent for {name}; retrieve authentically before verification"
                    farm_response = client.post("/api/farms", json={
                        "name": "ROLLBACK-ONLY ML recovery " + name,
                        "locationName": name, "latitude": lat, "longitude": lon,
                        "currentCrop": "Wheat", "irrigation": "rainfed", "goal": "soil_health"})
                    assert farm_response.status_code == 201, farm_response.text
                    farm = farm_response.json()
                    assert (farm["latitude"], farm["longitude"]) == (lat, lon)
                    assert other.get(f"/api/farms/{farm['id']}").status_code == 404
                    plan_response = client.post(f"/api/farms/{farm['id']}/plans", json={})
                    assert plan_response.status_code == 201, plan_response.text
                    plan = plan_response.json()
                    ai = plan["aiIntegration"]
                    assert not ai["model"]["predictionsEnabled"]
                    assert all(not crop["available"] for crop in ai["coverage"])
                    assert ai["featurePreparation"]["modelFeatures"] is None
                    assert ai["featurePreparation"]["coordinates"]["latitude"] == lat
                    assert ai["featurePreparation"]["coordinates"]["longitude"] == lon
                    path = f"/api/farms/{farm['id']}/plans/{plan['id']}"
                    reopened = client.get(path)
                    assert reopened.status_code == 200
                    assert reopened.json()["aiIntegration"] == ai
                    assert other.get(path).status_code == 404
                    assert other.post(f"/api/farms/{farm['id']}/plans", json={}).status_code == 404
                    results[name] = {
                        "coordinates": [lat, lon], "owner_isolation": "passed",
                        "report_created_reopened_snapshot_equal": True,
                        "historical_climate_prepared": "climate_features" in historical,
                        "historical_full_vector_prepared": historical["compatible"],
                        "historical_preparation_reasons": historical["reasons"],
                        "model_enabled": False, "estimator_executed": False,
                        "model_input_in_live_planner": ai["featurePreparation"]["modelFeatures"],
                        "planner_use": ai["plannerUse"], "schema": ai["adapterVersion"],
                        "coverage": ai["coverage"],
                        "dashboard_period": ai["featurePreparation"]["referencePeriod"],
                        "required_ml_period": ai["featurePreparation"]["requiredReferencePeriod"],
                        "unavailable_reasons": ai["featurePreparation"]["unavailableReasons"],
                    }
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
    result = {"generated_at": now(), "accuracy_benchmark": False,
              "session_type": "signed browser-session ownership, not account authentication",
              "data_mutations_rolled_back": True, "locations": results}
    write_json(out, result)
    print(f"{len(results)} real-data API location checks passed; all test mutations rolled back")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operational", default="generated-artifacts/ml-recovery/operational/five-locations.json")
    parser.add_argument("--out", default="docs/ml-recovery/evidence/five-location-api.json")
    args = parser.parse_args()
    if Path(args.out).exists():
        raise ValueError("Evidence exists; choose a new output path")
    run(args.operational, args.out)
