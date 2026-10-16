BOOK = dict(role="Carpenter", jurisdiction="NZ", employment_basis="permanent", source_date="2012", evidence="market normalised", hourly_rate=25, paid_hours_week=45,
            productive_hours_week=38, kiwisaver_pct="0.02", annual_leave_days=20, stat_days=11, sick_days=5, days_per_week=5, levy_pct="0.0635",
            redundancy_pct="0.02", weekly_allowance=45, supervision_pct="0.05")


def test_calc_shows_the_build_up_and_explains_bad_input(client, auth):
    r = client.post("/api/labour/calc", headers=auth, json=BOOK)
    assert r.status_code == 200 and r.json()["rate"] == 41.04 and r.json()["status"] == "AMBER" and r.json()["steps"][0]["label"] == "Weekly pay"
    bad = client.post("/api/labour/calc", headers=auth, json={**BOOK, "productive_hours_week": 60})
    assert bad.status_code == 422 and "exceed paid" in bad.json()["detail"]
    assert client.post("/api/labour/calc", json=BOOK).status_code == 401
