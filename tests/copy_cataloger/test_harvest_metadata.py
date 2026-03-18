"""Tests for skills/copy-cataloger/scripts/harvest_metadata.py

Uses respx to mock httpx calls and avoids real network I/O.
"""

import pytest
import respx
import httpx

import harvest_metadata as hm


MINIMAL_MARCXML = (
    '<?xml version="1.0"?>'
    '<collection xmlns="http://www.loc.gov/MARC21/slim">'
    '<marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">'
    '<marc:leader>00000nam a2200000   4500</marc:leader>'
    '<marc:controlfield tag="001">ocn123456789</marc:controlfield>'
    '<marc:datafield tag="245" ind1="1" ind2="0">'
    '<marc:subfield code="a">The great Gatsby</marc:subfield>'
    '</marc:datafield>'
    '</marc:record>'
    '</collection>'
)

SRU_HIT_RESPONSE = (
    '<?xml version="1.0"?>'
    '<searchRetrieveResponse>'
    '<numberOfRecords>1</numberOfRecords>'
    '<records>'
    '<record>'
    '<recordData>'
    '<marc:record xmlns:marc="http://www.loc.gov/MARC21/slim">'
    '<marc:leader>00000nam a2200000   4500</marc:leader>'
    '<marc:controlfield tag="001">ocn123456789</marc:controlfield>'
    '</marc:record>'
    '</recordData>'
    '</record>'
    '</records>'
    '</searchRetrieveResponse>'
)

SRU_ZERO_RESPONSE = (
    '<?xml version="1.0"?>'
    '<searchRetrieveResponse>'
    '<numberOfRecords>0</numberOfRecords>'
    '</searchRetrieveResponse>'
)


# ─── _sru_query ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_sru_query_success():
    server = {"url": "https://lx2.loc.gov/sru/authorities", "type": "SRU", "database": "lcdb"}
    respx.get("https://lx2.loc.gov/sru/authorities").mock(
        return_value=httpx.Response(200, text=SRU_HIT_RESPONSE)
    )
    result = await hm._sru_query(server, 'bath.isbn="9780743273565"', timeout=10)
    assert "<marc:record" in result or "<record" in result


@pytest.mark.asyncio
@respx.mock
async def test_sru_query_zero_records():
    server = {"url": "https://lx2.loc.gov/sru/authorities", "type": "SRU", "database": "lcdb"}
    respx.get("https://lx2.loc.gov/sru/authorities").mock(
        return_value=httpx.Response(200, text=SRU_ZERO_RESPONSE)
    )
    result = await hm._sru_query(server, 'bath.isbn="0000000000"', timeout=10)
    assert result == "Record Not Found"


@pytest.mark.asyncio
@respx.mock
async def test_sru_query_network_error():
    server = {"url": "https://lx2.loc.gov/sru/authorities", "type": "SRU", "database": "lcdb"}
    respx.get("https://lx2.loc.gov/sru/authorities").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    with pytest.raises(httpx.ConnectError):
        await hm._sru_query(server, 'bath.isbn="9780743273565"', timeout=10)


# ─── harvest_metadata ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_harvest_metadata_unknown_source():
    result = await hm.harvest_metadata("9780743273565", "nonexistent_source")
    assert "Authentication Failure" in result


@pytest.mark.asyncio
async def test_harvest_metadata_sru_success(monkeypatch):
    async def mock_sru(server, query, timeout):
        return MINIMAL_MARCXML

    monkeypatch.setattr(hm, "_sru_query", mock_sru)
    result = await hm.harvest_metadata("9780743273565", "loc")
    assert "collection" in result or "marc:record" in result


@pytest.mark.asyncio
async def test_harvest_metadata_propagates_not_found(monkeypatch):
    async def mock_sru(server, query, timeout):
        return "Record Not Found"

    monkeypatch.setattr(hm, "_sru_query", mock_sru)
    result = await hm.harvest_metadata("0000000000000", "loc")
    assert result == "Record Not Found"
