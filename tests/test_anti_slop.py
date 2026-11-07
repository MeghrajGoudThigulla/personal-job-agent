from app.intelligence.anti_slop import AntiSlopValidator

def test_anti_slop_catches_buzzwords():
    validator = AntiSlopValidator()
    slop_text = "I am a passionate and results-driven engineer who leverages cutting-edge technology to build seamless, robust, and game-changing solutions."
    res = validator.evaluate_text(slop_text)
    assert res["is_clean"] is False
    assert res["score"] > 30.0
    assert "seamless" in res["detected_words"]
    assert "cutting-edge" in res["detected_words"]

def test_anti_slop_accepts_authentic_metrics():
    validator = AntiSlopValidator()
    clean_text = "Delivered backend infrastructure of 286 endpoints, 61+ database models, and 30+ Alembic migrations across multiple production products, owning schema design end to end."
    res = validator.evaluate_text(clean_text)
    assert res["is_clean"] is True
    assert res["score"] <= 20.0
    assert len(res["detected_words"]) == 0
