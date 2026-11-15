"""E311 (missing enum provenance) fires only for a declared parameter enum."""
import pytest

from specdev_tools.validation.validators.step_05 import validate_step_05

_PROVENANCE = {"source_url": "https://www.iso.org/iso-4217-currency-codes.html"}
_ENUM_PARAM = {"name": "currency", "in": "query", "required": True, "enum": ["USD", "EUR"]}


def _api(**extra):
    return {"api_id": "api-pay", "method": "POST", "path": "/pay", **extra}


def _e311(api):
    return [e for e in validate_step_05({"apis": [api]}, ".") if "E311" in e.render()]


def test_errors_only_api_without_provenance_no_e311():
    api = _api(errors=[{"code": "card-declined"}], error_codes=["card-declined"])
    assert _e311(api) == []


def test_parameter_enum_without_provenance_fires_e311():
    assert len(_e311(_api(parameters=[_ENUM_PARAM]))) == 1


def test_parameter_enum_with_provenance_clean():
    assert _e311(_api(parameters=[_ENUM_PARAM], enum_provenance=_PROVENANCE)) == []


@pytest.mark.parametrize(
    ("api", "fires"),
    [
        (_api(parameters=[_ENUM_PARAM]), True),
        (_api(parameters=[_ENUM_PARAM], relies_on=["tp-bank"]), True),
        (_api(parameters=[_ENUM_PARAM], enum_provenance=_PROVENANCE), False),
        (_api(parameters=[{"name": "id", "in": "path", "required": True}]), False),
        (_api(errors=[{"code": "x"}]), False),
        (_api(), False),
    ],
    ids=["enum", "enum-relies-on", "enum-provenance", "plain-param", "errors-only", "bare"],
)
def test_e311_reading_table(api, fires):
    assert bool(_e311(api)) is fires
