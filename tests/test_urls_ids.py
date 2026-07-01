from scraper import urls, ids


def test_urls_paths():
    assert urls.season("s26") == "/s26/"
    assert urls.regatta("s26", "hood") == "/s26/hood/"
    assert urls.full_scores("s26", "hood") == "/s26/hood/full-scores/"
    assert urls.division("s26", "hood", "A") == "/s26/hood/A/"
    assert urls.divisions("s26", "hood") == "/s26/hood/divisions/"
    assert urls.all_races("s26", "hood") == "/s26/hood/all/"
    assert urls.rotations("s26", "hood") == "/s26/hood/rotations/"
    assert urls.sailors("s26", "hood") == "/s26/hood/sailors/"
    assert urls.school("navy", "s26") == "/schools/navy/s26/"


def test_school_slug():
    assert ids.school_slug("/schools/navy/s26/") == "navy"
    assert ids.school_slug("/schools/st-marys/f25/") == "st-marys"
    assert ids.school_slug("/navy/s26/") == "navy"          # bare form
    assert ids.school_slug("/not-a-school") == ""


def test_sailor_slug():
    assert ids.sailor_slug("/sailors/john-doe/") == "john-doe"
    assert ids.sailor_slug("/sailors/jane-doe-1/") == "jane-doe-1"
    assert ids.sailor_slug("/schools/navy/s26/") == ""


def test_split_sailor_name():
    assert ids.split_sailor_name("Jane Doe '26") == ("Jane", "Doe", 2026, True)
    assert ids.split_sailor_name("Jane Doe '26 *") == ("Jane", "Doe", 2026, False)
    assert ids.split_sailor_name("John Smith '99") == ("John", "Smith", 1999, True)
    assert ids.split_sailor_name("Coach Bob") == ("Coach", "Bob", None, True)
    # unknown-year marker stripped, no year
    first, last, year, reg = ids.split_sailor_name("Al Green '??")
    assert (first, last, year, reg) == ("Al", "Green", None, True)


def test_expand_races():
    assert ids.expand_races("1-3,5", list(range(1, 15))) == [1, 2, 3, 5]
    assert ids.expand_races("7", [1, 2, 7]) == [7]
    assert ids.expand_races("1-3", []) == [1, 2, 3]
    # empty range == all races
    assert ids.expand_races("", [1, 2, 3]) == [1, 2, 3]
    assert ids.expand_races("  ", [4, 5]) == [4, 5]
