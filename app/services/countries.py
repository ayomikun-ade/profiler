import pycountry


def country_name_from_code(code: str) -> str:
    if not code:
        return ""
    country = pycountry.countries.get(alpha_2=code.upper())
    return country.name if country else code


def country_code_from_name(name: str) -> str | None:
    if not name:
        return None
    lookup = name.strip()
    country = pycountry.countries.get(name=lookup)
    if country is not None:
        return country.alpha_2
    try:
        matches = pycountry.countries.search_fuzzy(lookup)
    except LookupError:
        return None
    return matches[0].alpha_2 if matches else None
