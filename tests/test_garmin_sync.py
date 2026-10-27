import io
import zipfile
from datetime import date

from garminconnect import GarminConnectTooManyRequestsError

from src.ingestion.garmin_sync import extract_fit, is_ride, read_state, sync_activities

FAKE_FIT = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT" + b"\x00" * 20


def zipped(data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("12345_ACTIVITY.fit", data)
    return buffer.getvalue()


def make_activity(activity_id: int, start: str, type_key: str = "road_biking") -> dict:
    return {"activityId": activity_id, "activityName": f"Salida {activity_id}",
            "startTimeLocal": start, "activityType": {"typeKey": type_key}}


class FakeGarmin:
    def __init__(self, activities, fail_on=None):
        self.activities = activities
        self.fail_on = fail_on
        self.downloaded = []
        self.requested_start = None

    def get_activities_by_date(self, startdate, enddate=None):
        self.requested_start = startdate
        return [a for a in self.activities if startdate <= a["startTimeLocal"][:10] <= enddate]

    def download_activity(self, activity_id, dl_fmt=None):
        if activity_id == self.fail_on:
            raise GarminConnectTooManyRequestsError("429")
        self.downloaded.append(activity_id)
        return zipped(FAKE_FIT)


def test_is_ride_recognises_cycling_types():
    assert is_ride(make_activity(1, "", "road_biking"))
    assert is_ride(make_activity(1, "", "indoor_cycling"))
    assert is_ride(make_activity(1, "", "gravel_cycling"))
    assert not is_ride(make_activity(1, "", "running"))


def test_extract_fit_from_zip_or_raw():
    assert extract_fit(zipped(FAKE_FIT)) == FAKE_FIT
    assert extract_fit(FAKE_FIT) == FAKE_FIT
    assert extract_fit(b"no es un archivo") is None


def test_sync_downloads_only_new_rides(tmp_path):
    activities = [
        make_activity(1, "2026-09-26 08:00:00"),
        make_activity(2, "2026-09-28 08:00:00", "running"),
        make_activity(3, "2026-10-02 08:00:00"),
        make_activity(4, "2026-09-20 08:00:00"),  # Antes de la fecha de inicio
    ]
    api = FakeGarmin(activities)
    result = sync_activities(api, folder=tmp_path, since=date(2026, 9, 25), until=date(2026, 10, 27))
    assert result.error is None
    assert api.downloaded == [1, 3]
    assert sorted(p.name for p in tmp_path.glob("*.fit")) == ["garmin_1.fit", "garmin_3.fit"]

    # Segunda ejecución: ventana incremental y nada que descargar
    api.downloaded.clear()
    sync_activities(api, folder=tmp_path, since=date(2026, 9, 25), until=date(2026, 10, 27))
    assert api.downloaded == []
    assert api.requested_start == "2026-09-25"  # 2 oct menos 7 días queda antes del inicio
    assert read_state(tmp_path)["last_sync"] > 0


def test_sync_keeps_progress_when_rate_limited(tmp_path):
    activities = [make_activity(1, "2026-09-26 08:00:00"), make_activity(2, "2026-09-27 08:00:00")]
    result = sync_activities(FakeGarmin(activities, fail_on=2), folder=tmp_path,
                             since=date(2026, 9, 25), until=date(2026, 10, 27))
    assert "limitó" in result.error
    assert [p.name for p in tmp_path.glob("*.fit")] == ["garmin_1.fit"]

    api = FakeGarmin(activities)
    sync_activities(api, folder=tmp_path, since=date(2026, 9, 25), until=date(2026, 10, 27))
    assert api.downloaded == [2]


def test_sync_includes_start_day_and_today(tmp_path):
    today = date.today()
    activities = [
        make_activity(1, "2026-09-24 23:30:00"),  # Un día antes: fuera
        make_activity(2, "2026-09-25 06:00:00"),  # El día de inicio: dentro
        make_activity(3, f"{today.isoformat()} 18:00:00"),  # Hoy: dentro
    ]
    api = FakeGarmin(activities)
    sync_activities(api, folder=tmp_path, since=date(2026, 9, 25))
    assert api.downloaded == [2, 3]
