# pylint: disable=C0415, W0613, W0621

from .conftest import anyhow_get_test_client
from .test_run_cwltool import run_cwltool_remote_wf


def test_get_runs(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    run_id = run_cwltool_remote_wf(client)  # type: ignore

    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()

    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == run_id


def add_dummy_data():  # type: ignore
    from sapporo.database import add_run_db
    from sapporo.schemas import RunSummary, State

    add_run_db(RunSummary(start_time="2024-01-01T10:00:00", run_id="63d1f6b7-1cfe-44b3-9f66-1640496b1b01", state=State.INITIALIZING, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-02T10:00:00", run_id="4f3de7a3-acb2-4568-b046-5bb7e63fa84c", state=State.RUNNING, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-03T10:00:00", run_id="f3e9f3b7-1cfe-44b3-9f66-1640496b1b01", state=State.RUNNING, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-04T10:00:00", run_id="47174545-1e16-4374-9412-d8c7f8293452", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-05T10:00:00", run_id="b7a3f3e9-1cfe-44b3-9f66-1640496b1b01", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-06T10:00:00", run_id="915350fe-b06c-4802-9518-241e900e437b", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-07T10:00:00", run_id="d8c7f829-1cfe-44b3-9f66-1640496b1b01", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-08T10:00:00", run_id="b67c3fab-7e85-49f4-a602-96614678501a", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-09T10:00:00", run_id="e437b915-1cfe-44b3-9f66-1640496b1b01", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-10T10:00:00", run_id="78501ab6-7e85-49f4-a602-96614678501a", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-11T10:00:00", run_id="be425612-373b-4dd6-80ad-eab3a70d9926", state=State.COMPLETE, end_time=None, tags={}))
    add_run_db(RunSummary(start_time="2024-01-12T10:00:00", run_id="660e5aa8-d656-4e1a-b6f8-7dc63c76f9b5", state=State.COMPLETE, end_time=None, tags={}))


def test_get_runs_with_dummy_db(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()

    # Default page_size is 10
    assert len(data["runs"]) == 10
    # Default sort_order is "desc"
    assert data["runs"][0]["start_time"] == "2024-01-12T10:00:00"


def test_get_runs_page_token(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()
    next_page_token = data["next_page_token"]

    response = client.get(f"/runs?page_token={next_page_token}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 2
    assert data["next_page_token"] is None


def test_get_runs_page_size(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs?page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 5

    response = client.get("/runs?page_size=15")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 12


def test_get_runs_sort_order(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs?sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["start_time"] == "2024-01-01T10:00:00"

    response = client.get("/runs?sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["start_time"] == "2024-01-12T10:00:00"


def test_get_runs_state(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs?state=INITIALIZING")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 1

    response = client.get("/runs?state=RUNNING")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 2


def test_get_runs_run_ids(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    add_dummy_data()  # type: ignore

    response = client.get("/runs?run_ids=63d1f6b7-1cfe-44b3-9f66-1640496b1b01&run_ids=4f3de7a3-acb2-4568-b046-5bb7e63fa84c")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 2


def test_get_runs_latest(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    run_id = run_cwltool_remote_wf(client)  # type: ignore

    response = client.get("/runs?latest=true")
    assert response.status_code == 200
    data = response.json()

    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == run_id
