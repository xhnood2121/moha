from moha.utils.time_utils import is_weekend, session_name


def test_session_names_by_hour():
    ms = 1_704_067_200_000  # 2024-01-01 00:00:00 UTC (Monday)
    assert session_name(ms) == "ASIA"
    assert session_name(ms + 7 * 3600 * 1000) == "LONDON"
    assert session_name(ms + 13 * 3600 * 1000) == "OVERLAP"
    assert session_name(ms + 16 * 3600 * 1000) == "NY_PM"
    assert session_name(ms + 21 * 3600 * 1000) == "OFF"


def test_weekend_definition():
    # 2024-01-05 = Friday
    fri_2100 = 1_704_486_000_000  # Fri 21:00 UTC
    fri_2300 = 1_704_493_200_000  # Fri 23:00 UTC
    sat_1000 = 1_704_535_200_000  # Sat 10:00 UTC
    mon_0100 = 1_704_675_600_000  # Mon 01:00 UTC
    assert not is_weekend(fri_2100)
    assert is_weekend(fri_2300)
    assert is_weekend(sat_1000)
    assert not is_weekend(mon_0100)
