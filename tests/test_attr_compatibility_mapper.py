from __future__ import annotations

from app.core.attr_compatibility_mapper import (
    list_mapping_profiles,
    map_attr_value_to_dword,
)


def test_list_mapping_profiles_contains_expected_profiles() -> None:
    profiles = list_mapping_profiles()
    assert "candidate_v1" in profiles
    assert "exe_compat_v1" in profiles
    assert "exe_compat_v2" in profiles


def test_exe_compat_profile_keeps_attribute0_to_5_compact() -> None:
    assert map_attr_value_to_dword(0, "exe_compat_v1") == 0x00000000
    assert map_attr_value_to_dword(1, "exe_compat_v1") == 0x00000001
    assert map_attr_value_to_dword(2, "exe_compat_v1") == 0x00000002
    assert map_attr_value_to_dword(3, "exe_compat_v1") == 0x00000003
    assert map_attr_value_to_dword(4, "exe_compat_v1") == 0x00000004
    assert map_attr_value_to_dword(5, "exe_compat_v1") == 0x00000005


def test_exe_compat_v2_ignores_family_overlay_bits() -> None:
    assert map_attr_value_to_dword(0xC8, "exe_compat_v2") == 0x00000000
    assert map_attr_value_to_dword(0xC9, "exe_compat_v2") == 0x00000001
    assert map_attr_value_to_dword(0xCB, "exe_compat_v2") == 0x00000003
    assert map_attr_value_to_dword(0x48, "exe_compat_v2") == 0x00000000
    assert map_attr_value_to_dword(0x0B, "exe_compat_v2") == 0x00000003
