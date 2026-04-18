def classify_age(age: int) -> str:
    if age <= 12:
        return "child"
    if age <= 19:
        return "teenager"
    if age <= 59:
        return "adult"
    return "senior"


def pick_top_country(countries: list[dict]) -> tuple[str, float]:
    top = max(countries, key=lambda c: c.get("probability", 0))
    return top["country_id"], float(top["probability"])
