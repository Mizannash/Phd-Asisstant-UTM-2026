import pytest
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.tools.prefilter import prefilter_openalex_results
import yaml

@pytest.fixture
def override_filters(tmp_path, monkeypatch):
    # Create a temporary filters.yaml
    filters = {
        "queries": [],
        "exclusions": ["Indonesia", "SMK", "SMKs"],
        "inclusions": ["Kolej Vokasional", "TVET Malaysia"],
        "threshold": 1
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "filters.yaml"
    with open(config_path, "w") as f:
        yaml.dump(filters, f)
        
    def mock_load_filters():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
            
    monkeypatch.setattr("src.tools.prefilter.load_filters", mock_load_filters)
    return filters

@pytest.fixture
def mock_db(monkeypatch):
    class MockLibraryDB:
        def check_status(self, title):
            if "Already in Library" in title:
                return {"status": "analyzed"}
            return None
    monkeypatch.setattr("src.tools.prefilter.LibraryDB", MockLibraryDB)

def test_indonesian_title_excluded(override_filters, mock_db):
    raw = [{
        "title": "Pendidikan Vokasi di Indonesia",
        "abstract": "This is a paper about Indonesia.",
        "institutions": "Universitas Indonesia",
        "doi": "10.123/1"
    }]
    survivors = prefilter_openalex_results(raw)
    assert len(survivors) == 0

def test_malaysian_kv_title_kept(override_filters, mock_db):
    raw = [{
        "title": "Pelaksanaan amali di Kolej Vokasional Malaysia",
        "abstract": "This is a paper about KV.",
        "institutions": "UTM",
        "doi": "10.123/2"
    }]
    survivors = prefilter_openalex_results(raw)
    assert len(survivors) == 1
    assert survivors[0]["relevance_score_prefilter"] >= 1

def test_already_in_library_skipped(override_filters, mock_db):
    raw = [{
        "title": "Already in Library: Kolej Vokasional Study",
        "abstract": "Good abstract.",
        "institutions": "",
        "doi": "10.123/3"
    }]
    survivors = prefilter_openalex_results(raw)
    assert len(survivors) == 0

def test_indonesia_in_abstract_but_strong_signal_in_title(override_filters, mock_db):
    # paper whose abstract mentions Indonesia but title is Malaysian TVET must SURVIVE prefilter
    raw = [{
        "title": "TVET Malaysia: A Comparative Study",
        "abstract": "We compare TVET Malaysia with vocational education in Indonesia.",
        "institutions": "Malaysian Institute",
        "doi": "10.123/4"
    }]
    survivors = prefilter_openalex_results(raw)
    assert len(survivors) == 1

def test_zero_survivors(override_filters, mock_db):
    raw = [
        {"title": "Random Paper", "abstract": "No signals here.", "doi": "10.123/5"},
        {"title": "Another random paper", "abstract": "Still nothing.", "doi": "10.123/6"}
    ]
    survivors = prefilter_openalex_results(raw)
    assert len(survivors) == 0

def test_smk_word_boundary(override_filters, mock_db):
    raw_excluded = [{
        "title": "Implementation of TVET in SMK",
        "abstract": "...",
        "doi": "10.123/7"
    }]
    survivors_excluded = prefilter_openalex_results(raw_excluded)
    assert len(survivors_excluded) == 0
    
    # "SMK" as substring of a larger word shouldn't trigger exclusion
    raw_included = [{
        "title": "Kolej Vokasional: Osmkosis process in biology", # 'smk' is inside Osmkosis
        "abstract": "...",
        "doi": "10.123/8"
    }]
    survivors_included = prefilter_openalex_results(raw_included)
    assert len(survivors_included) == 1
