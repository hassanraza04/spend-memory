from pathlib import Path

from app.main import create_app
from fastapi import Query
from fastapi.testclient import TestClient
from pydantic import ValidationError
from spend_memory.api.contracts import (
    ErrorDetail,
    PageRequest,
    TransactionPath,
    TransactionQuery,
)
from spend_memory.api.errors import ApiError
from starlette.exceptions import HTTPException


def test_unknown_route_uses_safe_error_envelope(tmp_path: Path) -> None:
    response = TestClient(
        create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    ).get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found.",
            "details": [],
        }
    }


def test_not_found_errors_preserve_safe_response_headers(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.get("/api/v1/not-found-header-probe")
    def not_found_header_probe() -> None:
        raise HTTPException(status_code=404, headers={"X-Request-Id": "local-test"})

    response = TestClient(app).get("/api/v1/not-found-header-probe")

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "local-test"


def test_http_errors_preserve_safe_response_headers(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.get("/api/v1/header-probe")
    def header_probe() -> None:
        raise HTTPException(status_code=405, headers={"Allow": "GET"})

    response = TestClient(app).get("/api/v1/header-probe")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"


def test_openapi_declares_error_envelopes(tmp_path: Path) -> None:
    schema = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data").openapi()
    responses = schema["paths"]["/api/v1/health"]["get"]["responses"]

    for status_code in ("404", "422", "500"):
        assert responses[status_code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }


def test_domain_errors_use_the_stable_error_envelope(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.get("/api/v1/domain-error-probe")
    def domain_error_probe() -> None:
        raise ApiError(
            "invalid_filter",
            "The date range is not valid.",
            422,
            (ErrorDetail(field="after", code="after_must_precede_before"),),
        )

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/domain-error-probe")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_filter",
            "message": "The date range is not valid.",
            "details": [{"field": "after", "code": "after_must_precede_before"}],
        }
    }


def test_shared_paging_contract_rejects_out_of_bounds_values() -> None:
    for values in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        try:
            PageRequest.model_validate(values)
        except ValidationError:
            continue
        raise AssertionError(f"expected validation failure for {values}")


def test_shared_transaction_contract_rejects_invalid_ids_and_sort_keys() -> None:
    try:
        TransactionPath.model_validate({"transaction_id": "not-a-uuid"})
    except ValidationError:
        pass
    else:
        raise AssertionError("expected invalid UUID to fail validation")

    try:
        TransactionQuery.model_validate({"sort": "description"})
    except ValidationError:
        pass
    else:
        raise AssertionError("expected unsupported sort key to fail validation")


def test_validation_errors_use_the_safe_error_envelope(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.get("/api/v1/paging-probe")
    def paging_probe(limit: int = Query(ge=1, le=100)) -> dict[str, int]:
        return {"limit": limit}

    response = TestClient(app).get("/api/v1/paging-probe?limit=0")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "The request is not valid.",
            "details": [{"field": "query.limit", "code": "greater_than_equal"}],
        }
    }


def test_unexpected_errors_do_not_expose_exception_details(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.get("/api/v1/failure-probe")
    def failure_probe() -> None:
        raise RuntimeError("private parser failure")

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/failure-probe")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "The request could not be completed.",
            "details": [],
        }
    }


def test_local_api_rejects_cross_origin_mutations(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")

    @app.post("/api/v1/mutation-probe")
    def mutation_probe() -> dict[str, str]:
        return {"status": "changed"}

    response = TestClient(app).post(
        "/api/v1/mutation-probe",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "cross_origin_request",
            "message": "This local request is not allowed.",
            "details": [],
        }
    }
