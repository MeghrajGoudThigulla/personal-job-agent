import pytest
from app.scrapers.search_dorks import SearchDorksScraper

@pytest.mark.asyncio
async def test_personalized_queries_coverage():
    scraper = SearchDorksScraper()
    assert len(scraper.queries_data) == 11, "Must contain all 11 target roles"
    assert len(scraper.flat_queries) == 121, "Must contain all 121 ATS dork queries"
    
    # Check Role 1
    r1 = scraper.flat_queries[0]
    assert r1["index"] == 1
    assert "Backend Engineer" in r1["role_title"]
    assert "Python" in r1["tech_stack"]
    assert "site:jobs.ashbyhq.com" in r1["site"]
    assert "India" in r1["location"]

    # Check Role 8 (Flutter)
    flutter_q = [q for q in scraper.flat_queries if "Flutter" in q["role_title"]]
    assert len(flutter_q) == 11, "Flutter role must have 11 platform queries"
    assert "Dart" in flutter_q[0]["tech_stack"] or "Flutter" in flutter_q[0]["tech_stack"]

    # Check Role 11 (Forward Deployed)
    fde_q = [q for q in scraper.flat_queries if "Forward Deployed" in q["role_title"]]
    assert len(fde_q) == 11, "Forward Deployed role must have 11 platform queries"

@pytest.mark.asyncio
async def test_round_robin_batch_progression():
    scraper = SearchDorksScraper()
    total = len(scraper.flat_queries)
    assert total == 121
    
    # Batch 1 (start 0, size 8)
    batch_1, next_1 = scraper.get_batch(0, 8)
    assert len(batch_1) == 8
    assert batch_1[0]["index"] == 1
    assert batch_1[-1]["index"] == 8
    assert next_1 == 8

    # Batch 2 (start 8, size 8)
    batch_2, next_2 = scraper.get_batch(next_1, 8)
    assert len(batch_2) == 8
    assert batch_2[0]["index"] == 9
    assert batch_2[-1]["index"] == 16
    assert next_2 == 16

    # Test Wrap-Around
    batch_wrap, next_wrap = scraper.get_batch(118, 8)
    assert len(batch_wrap) == 8
    wrap_indices = [q["index"] for q in batch_wrap]
    assert wrap_indices == [119, 120, 121, 1, 2, 3, 4, 5]
    assert next_wrap == 5

@pytest.mark.asyncio
async def test_dorks_rotation_status_endpoint():
    scraper = SearchDorksScraper()
    status = await scraper.get_status()
    assert status["total_queries"] == 121
    assert status["batch_size"] == 8
    assert status["total_batches"] == 16
    assert "current_cursor" in status
    assert "active_batch_queries" in status
    assert len(status["active_batch_queries"]) == 8
