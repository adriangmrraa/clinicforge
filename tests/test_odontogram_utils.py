"""Tests para shared/odontogram_utils.py — Parser unificado v3.0"""
import pytest
import json

from shared.odontogram_utils import (
    normalize_to_v3,
    build_default_permanent_teeth,
    build_default_deciduous_teeth,
    compute_global_state,
    LEGACY_STATE_MAP,
    ALL_PERMANENT_FDI,
    ALL_DECIDUOUS_FDI,
    SURFACE_KEYS,
    VALID_PERMANENT_FDI,
    VALID_DECIDUOUS_FDI,
)


class TestBuildDefaults:
    """Tests para build_default_permanent_teeth y build_default_deciduous_teeth"""

    def test_permanent_returns_32_teeth(self):
        teeth = build_default_permanent_teeth()
        assert len(teeth) == 32

    def test_deciduous_returns_20_teeth(self):
        teeth = build_default_deciduous_teeth()
        assert len(teeth) == 20

    def test_permanent_fdi_numbers(self):
        teeth = build_default_permanent_teeth()
        ids = [t["id"] for t in teeth]
        assert set(ids) == VALID_PERMANENT_FDI

    def test_deciduous_fdi_numbers(self):
        teeth = build_default_deciduous_teeth()
        ids = [t["id"] for t in teeth]
        assert set(ids) == VALID_DECIDUOUS_FDI

    def test_all_teeth_healthy(self):
        for teeth_fn in [build_default_permanent_teeth, build_default_deciduous_teeth]:
            teeth = teeth_fn()
            for tooth in teeth:
                assert tooth["state"] == "healthy"
                for sk in SURFACE_KEYS:
                    assert tooth["surfaces"][sk]["state"] == "healthy"
                    assert tooth["surfaces"][sk]["condition"] is None
                    assert tooth["surfaces"][sk]["color"] is None

    def test_tooth_has_5_surfaces(self):
        teeth = build_default_permanent_teeth()
        for tooth in teeth:
            assert set(tooth["surfaces"].keys()) == set(SURFACE_KEYS)


class TestNormalizeToV3:
    """Tests para normalize_to_v3"""

    # ── Input None / inválido ──

    def test_none_returns_valid_v3(self):
        result = normalize_to_v3(None)
        assert result["version"] == "3.0"
        assert "permanent" in result
        assert "deciduous" in result
        assert len(result["permanent"]["teeth"]) == 32
        assert len(result["deciduous"]["teeth"]) == 20

    def test_empty_string_returns_default(self):
        result = normalize_to_v3("")
        assert result["version"] == "3.0"

    def test_invalid_json_string_returns_default(self):
        result = normalize_to_v3("{not valid json}")
        assert result["version"] == "3.0"

    def test_integer_returns_default(self):
        result = normalize_to_v3(42)
        assert result["version"] == "3.0"

    def test_empty_dict_returns_default(self):
        result = normalize_to_v3({})
        assert result["version"] == "3.0"

    # ── v1 Legacy Format ──

    def test_v1_simple_string_states(self):
        v1 = {"18": "caries", "21": "healthy"}
        result = normalize_to_v3(v1)
        assert result["version"] == "3.0"
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        # All surfaces of tooth 18 should also be caries
        for sk in SURFACE_KEYS:
            assert perm_map[18]["surfaces"][sk]["state"] == "caries"

    def test_v1_object_states(self):
        v1 = {"37": {"status": "crown", "notes": "Corona de porcelana"}}
        result = normalize_to_v3(v1)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        # "crown" maps to "corona_porcelana" via LEGACY_STATE_MAP
        assert perm_map[37]["state"] == "corona_porcelana"
        assert perm_map[37]["notes"] == "Corona de porcelana"

    def test_v1_with_surfaces(self):
        v1 = {"16": {"status": "caries", "surfaces": {"occlusal": "caries", "mesial": "treated"}}}
        result = normalize_to_v3(v1)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[16]["surfaces"]["occlusal"]["state"] == "caries"
        # "treated" maps to "restauracion_resina"
        assert perm_map[16]["surfaces"]["mesial"]["state"] == "restauracion_resina"

    def test_v1_invalid_fdi_ignored(self):
        v1 = {"99": "caries", "18": "caries"}
        result = normalize_to_v3(v1)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        # 99 is not a valid FDI, should be ignored

    def test_v1_as_json_string(self):
        v1 = json.dumps({"18": "caries"})
        result = normalize_to_v3(v1)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"

    # ── v2.0 Format ──

    def test_v2_basic(self):
        v2 = {
            "version": "2.0",
            "teeth": [
                {"id": 18, "state": "caries", "surfaces": {}, "notes": "Test"},
                {"id": 21, "state": "restoration", "surfaces": {}, "notes": ""},
            ],
            "last_updated": "2026-01-01T00:00:00Z"
        }
        result = normalize_to_v3(v2)
        assert result["version"] == "3.0"
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"
        assert perm_map[18]["notes"] == "Test"
        # "restoration" maps to "restauracion_resina"
        assert perm_map[21]["state"] == "restauracion_resina"

    def test_v2_preserves_last_updated(self):
        v2 = {"teeth": [{"id": 18, "state": "healthy"}], "last_updated": "2026-03-15T10:00:00Z"}
        result = normalize_to_v3(v2)
        assert result["last_updated"] == "2026-03-15T10:00:00Z"

    def test_v2_with_surface_strings(self):
        v2 = {
            "teeth": [
                {"id": 18, "state": "caries", "surfaces": {"occlusal": "caries", "mesial": "healthy"}}
            ]
        }
        result = normalize_to_v3(v2)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["surfaces"]["occlusal"]["state"] == "caries"
        assert perm_map[18]["surfaces"]["mesial"]["state"] == "healthy"

    def test_v2_without_version_field(self):
        """v2 without explicit version field (just has teeth array)"""
        v2 = {"teeth": [{"id": 18, "state": "implant"}]}
        result = normalize_to_v3(v2)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "implante"

    def test_v2_as_json_string(self):
        v2 = json.dumps({"teeth": [{"id": 18, "state": "caries"}], "version": "2.0"})
        result = normalize_to_v3(v2)
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["state"] == "caries"

    # ── v3.0 Format ──

    def test_v3_passthrough(self):
        v3 = {
            "version": "3.0",
            "last_updated": "2026-04-02T10:00:00Z",
            "active_dentition": "deciduous",
            "permanent": {
                "teeth": [{"id": 18, "state": "caries", "surfaces": {
                    "occlusal": {"state": "caries", "condition": "malo", "color": "#ef4444"},
                    "mesial": {"state": "healthy", "condition": None, "color": None},
                    "distal": {"state": "healthy", "condition": None, "color": None},
                    "buccal": {"state": "healthy", "condition": None, "color": None},
                    "lingual": {"state": "healthy", "condition": None, "color": None},
                }, "notes": "Test v3"}]
            },
            "deciduous": {
                "teeth": [{"id": 51, "state": "caries", "surfaces": {
                    "occlusal": {"state": "caries", "condition": "malo", "color": None},
                    "mesial": {"state": "healthy", "condition": None, "color": None},
                    "distal": {"state": "healthy", "condition": None, "color": None},
                    "buccal": {"state": "healthy", "condition": None, "color": None},
                    "lingual": {"state": "healthy", "condition": None, "color": None},
                }, "notes": ""}]
            }
        }
        result = normalize_to_v3(v3)
        assert result["version"] == "3.0"
        assert result["active_dentition"] == "deciduous"
        perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
        assert perm_map[18]["surfaces"]["occlusal"]["state"] == "caries"
        assert perm_map[18]["surfaces"]["occlusal"]["condition"] == "malo"
        assert perm_map[18]["surfaces"]["occlusal"]["color"] == "#ef4444"
        assert perm_map[18]["notes"] == "Test v3"

    def test_v3_fills_missing_teeth(self):
        """v3 with only 1 permanent tooth still returns 32 total"""
        v3 = {
            "version": "3.0",
            "permanent": {"teeth": [{"id": 18, "state": "caries", "surfaces": {}, "notes": ""}]},
            "deciduous": {"teeth": []}
        }
        result = normalize_to_v3(v3)
        assert len(result["permanent"]["teeth"]) == 32
        assert len(result["deciduous"]["teeth"]) == 20

    # ── Legacy State Mapping ──

    def test_all_legacy_states_map(self):
        for old_state, new_state in LEGACY_STATE_MAP.items():
            v1 = {"18": old_state}
            result = normalize_to_v3(v1)
            perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
            assert perm_map[18]["state"] == new_state, f"Failed mapping: {old_state} → {new_state}"

    # ── Structure Validation ──

    def test_result_always_has_required_keys(self):
        """Every result must have version, permanent, deciduous, active_dentition"""
        for input_val in [None, "", {}, {"18": "caries"}, {"teeth": []},
                          {"version": "3.0", "permanent": {"teeth": []}, "deciduous": {"teeth": []}}]:
            result = normalize_to_v3(input_val)
            assert "version" in result
            assert "permanent" in result
            assert "deciduous" in result
            assert "active_dentition" in result
            assert result["version"] == "3.0"


class TestComputeGlobalState:
    """Tests para compute_global_state"""

    def test_all_healthy(self):
        surfaces = {sk: {"state": "healthy"} for sk in SURFACE_KEYS}
        assert compute_global_state(surfaces) == "healthy"

    def test_all_same_non_healthy(self):
        surfaces = {sk: {"state": "caries"} for sk in SURFACE_KEYS}
        assert compute_global_state(surfaces) == "caries"

    def test_mixed_states(self):
        surfaces = {
            "occlusal": {"state": "caries"},
            "mesial": {"state": "restauracion_resina"},
            "distal": {"state": "healthy"},
            "buccal": {"state": "healthy"},
            "lingual": {"state": "healthy"},
        }
        # Two distinct non-healthy states → falls back to "healthy"
        assert compute_global_state(surfaces) == "healthy"

    def test_one_non_healthy(self):
        surfaces = {sk: {"state": "healthy"} for sk in SURFACE_KEYS}
        surfaces["occlusal"] = {"state": "caries"}
        assert compute_global_state(surfaces) == "caries"

    def test_empty_surfaces(self):
        assert compute_global_state({}) == "healthy"
