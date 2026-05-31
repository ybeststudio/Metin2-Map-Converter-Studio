from __future__ import annotations


MAPPING_PROFILES = {
    "candidate_v1": "Ilk aday mapping; bit ailelerini genisletilmis aday bayraklara cevirir.",
    "exe_compat_v1": "EXE incelemesine dayali daha kompakt mapping; Attribute0..5 temelini korur.",
    "exe_compat_v2": "Referans orneklerle uyumlu kompakt mapping; su an aile overlay'lerini eklemeden alt 3 biti korur.",
}


def list_mapping_profiles() -> dict[str, str]:
    return dict(MAPPING_PROFILES)


def map_attr_value_to_dword(value: int, mapping_profile: str = "candidate_v1") -> int:
    if mapping_profile == "candidate_v1":
        return map_attr_value_to_candidate_dword(value)
    if mapping_profile == "exe_compat_v1":
        return map_attr_value_to_exe_compat_dword(value)
    if mapping_profile == "exe_compat_v2":
        return map_attr_value_to_exe_compat_v2_dword(value)
    raise ValueError(f"Bilinmeyen mapping profile: {mapping_profile}")


def map_attr_value_to_candidate_dword(value: int) -> int:
    dword = 0
    family_base = value & 0xF8

    if value & 0x01:
        dword |= 1 << 0
    if value & 0x02:
        dword |= 1 << 1
    if value & 0x04:
        dword |= 1 << 2
    if 0x08 <= family_base < 0x40:
        dword |= 1 << 3
    if 0x40 <= family_base < 0x80:
        dword |= 1 << 4
    if family_base >= 0xC0:
        dword |= 1 << 5
    if value != 0:
        dword |= 1 << 6

    return dword


def map_attr_value_to_exe_compat_dword(value: int) -> int:
    family_base = value & 0xF8

    # Attribute0..5 siniflarina en yakin kompakt taban.
    dword = value & 0x07

    # EXE'deki water/safezone/mountain kontrol isimlerine gore aile overlay'leri.
    if 0x08 <= family_base < 0x40:
        dword |= 0x00000008
    if 0x40 <= family_base < 0x80:
        dword |= 0x00000010
    if family_base >= 0xC0:
        dword |= 0x00000020

    return dword


def map_attr_value_to_exe_compat_v2_dword(value: int) -> int:
    # Referans server_attr orneklerinde cok sayida map yalnizca compact
    # Attribute0..5 tabanini kullaniyor; aile overlay'leri fark uretiyor.
    return value & 0x07
