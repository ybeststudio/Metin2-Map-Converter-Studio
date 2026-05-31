from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.core.generation_workflow import run_selected_generation
from app.core.attr_dword_candidate_mapper import (
    build_batch_attr_dword_candidate_summary,
    write_attr_dword_candidate_report,
    write_batch_attr_dword_candidate_summary,
)
from app.core.attr_compatibility_mapper import list_mapping_profiles
from app.core.attr_dword_matrix_preview import (
    build_batch_attr_dword_matrix_preview_summary,
    write_attr_dword_matrix_preview,
    write_batch_attr_dword_matrix_preview_summary,
)
from app.core.attr_family_analyzer import (
    build_batch_attr_family_summary,
    write_attr_family_report,
    write_batch_attr_family_summary,
)
from app.core.bulk_generator import generate_bulk_outputs
from app.gui import run_gui
from app.core.map_reader import discover_map_sources, resolve_map_source_by_name
from app.core.raw_sectree_block_packer import (
    build_batch_raw_sectree_block_summary,
    write_batch_raw_sectree_block_summary,
    write_raw_sectree_block_report,
)
from app.core.server_attr_exporter import (
    export_server_attr_batch,
    is_lzo_backend_available,
    write_server_attr_batch_summary,
    write_server_attr_export_report,
)
from app.core.sectree_block_preview import (
    build_batch_sectree_block_preview_summary,
    write_batch_sectree_block_preview_summary,
    write_sectree_block_preview,
)
from app.core.server_attr_analyzer import (
    build_batch_attr_summary,
    find_matching_server_attr_sample,
    write_attr_analysis_report,
    write_batch_attr_summary,
)
from app.core.server_attr_block_diff import (
    build_batch_server_attr_block_diff_summary,
    write_batch_server_attr_block_diff_summary,
    write_server_attr_block_diff_report,
)
from app.core.setting_parser import parse_setting_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Metin2 Map Server Dosyasi Uretici MVP araci"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_setting_parser = subparsers.add_parser(
        "parse-setting",
        help="Tek bir Setting.txt dosyasini analiz et",
    )
    parse_setting_parser.add_argument(
        "setting_file",
        help="Analiz edilecek client Setting.txt dosyasinin yolu",
    )

    scan_maps_parser = subparsers.add_parser(
        "scan-maps",
        help="Kaynak dizindeki tum metin2_map_* klasorlerini bul ve output iskeletini uret",
    )
    scan_maps_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Taranacak ana dizin",
    )
    scan_maps_parser.add_argument(
        "--output-root",
        default=str(Path.cwd() / "GeneratedMaps"),
        help="Ciktilarin yazilacagi dizin",
    )
    scan_maps_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek Town.txt ve diger referanslar icin kullanilacak dizin",
    )

    generate_maps_parser = subparsers.add_parser(
        "generate-maps",
        help="Secilen map listesi icin nihai toplu output uret",
    )
    generate_maps_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Taranacak ana dizin",
    )
    generate_maps_parser.add_argument(
        "--output-root",
        default=str(Path.cwd() / "GeneratedMaps"),
        help="Ciktilarin yazilacagi dizin",
    )
    generate_maps_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek Town/NPC/Regen/Stone/Boss referanslari icin kullanilacak dizin",
    )
    generate_maps_parser.add_argument(
        "--report-file",
        default=str(Path.cwd() / "GeneratedMaps" / "_reports" / "generation_summary.json"),
        help="Yazilacak toplu ozet raporu yolu",
    )
    generate_maps_parser.add_argument(
        "--map-name",
        action="append",
        default=[],
        help="Uretilecek map adi; birden fazla kez verilebilir",
    )
    generate_maps_parser.add_argument(
        "--map-list-file",
        help="Satir satir map adlari iceren txt dosyasi",
    )

    subparsers.add_parser(
        "launch-gui",
        help="Masaustu arayuzu baslat",
    )

    analyze_attr_parser = subparsers.add_parser(
        "analyze-server-attr",
        help="Client attr.atr ve ornek server_attr dosyalarini karsilastirmali analiz et",
    )
    analyze_attr_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_attr_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_attr_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    analyze_attr_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "server_attr_analysis.json"),
        help="Yazilacak analiz raporu yolu",
    )

    analyze_attr_batch_parser = subparsers.add_parser(
        "analyze-server-attr-batch",
        help="Ornek server_attr bulunan tum mapler icin toplu karsilastirma raporu uret",
    )
    analyze_attr_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_attr_batch_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    analyze_attr_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "server_attr_batch_summary.json"),
        help="Yazilacak toplu analiz raporu yolu",
    )

    analyze_family_parser = subparsers.add_parser(
        "analyze-attr-family",
        help="Tek map icin attr deger ailelerini siniflandir ve raporla",
    )
    analyze_family_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_family_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_family_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_family_analysis.json"),
        help="Yazilacak attr family raporu yolu",
    )

    analyze_family_batch_parser = subparsers.add_parser(
        "analyze-attr-family-batch",
        help="Tum mapler icin attr deger aileleri toplu ozet raporu uret",
    )
    analyze_family_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_family_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_family_batch_summary.json"),
        help="Yazilacak toplu attr family raporu yolu",
    )

    analyze_dword_candidates_parser = subparsers.add_parser(
        "analyze-dword-candidates",
        help="Tek map icin attr -> dword aday rol raporu uret",
    )
    analyze_dword_candidates_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_dword_candidates_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_dword_candidates_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_dword_candidates.json"),
        help="Yazilacak candidate mapping raporu yolu",
    )

    analyze_dword_candidates_batch_parser = subparsers.add_parser(
        "analyze-dword-candidates-batch",
        help="Tum mapler icin attr -> dword aday rol ozeti uret",
    )
    analyze_dword_candidates_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_dword_candidates_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_dword_candidates_batch.json"),
        help="Yazilacak toplu candidate mapping raporu yolu",
    )

    analyze_dword_matrix_parser = subparsers.add_parser(
        "analyze-dword-matrix-preview",
        help="Tek map icin aday DWORD matrix preview raporu uret",
    )
    analyze_dword_matrix_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_dword_matrix_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_dword_matrix_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_dword_matrix_preview.json"),
        help="Yazilacak matrix preview raporu yolu",
    )
    analyze_dword_matrix_parser.add_argument(
        "--preview-width",
        type=int,
        default=16,
        help="Preview penceresi genisligi",
    )
    analyze_dword_matrix_parser.add_argument(
        "--preview-height",
        type=int,
        default=16,
        help="Preview penceresi yuksekligi",
    )

    analyze_dword_matrix_batch_parser = subparsers.add_parser(
        "analyze-dword-matrix-preview-batch",
        help="Tum mapler icin aday DWORD matrix preview ozet raporu uret",
    )
    analyze_dword_matrix_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_dword_matrix_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "attr_dword_matrix_preview_batch.json"),
        help="Yazilacak toplu matrix preview raporu yolu",
    )

    analyze_sectree_block_parser = subparsers.add_parser(
        "analyze-sectree-block-preview",
        help="Tek map icin sectree bazli DWORD block preview raporu uret",
    )
    analyze_sectree_block_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_sectree_block_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_sectree_block_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "sectree_block_preview.json"),
        help="Yazilacak sectree block preview raporu yolu",
    )
    analyze_sectree_block_parser.add_argument(
        "--sample-block-limit",
        type=int,
        default=8,
        help="Raporlanacak ilk block sayisi",
    )
    analyze_sectree_block_parser.add_argument(
        "--sample-rows",
        type=int,
        default=4,
        help="Her block icin yazilacak ornek satir sayisi",
    )
    analyze_sectree_block_parser.add_argument(
        "--sample-cols",
        type=int,
        default=8,
        help="Her block icin yazilacak ornek sutun sayisi",
    )

    analyze_sectree_block_batch_parser = subparsers.add_parser(
        "analyze-sectree-block-preview-batch",
        help="Tum mapler icin sectree block preview toplu ozeti uret",
    )
    analyze_sectree_block_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_sectree_block_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "sectree_block_preview_batch.json"),
        help="Yazilacak toplu sectree block preview raporu yolu",
    )

    analyze_raw_sectree_parser = subparsers.add_parser(
        "analyze-raw-sectree-packer",
        help="Tek map icin sikistirilmamis raw sectree block paketi raporu uret",
    )
    analyze_raw_sectree_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_raw_sectree_parser.add_argument(
        "--map-name",
        required=True,
        help="Analiz edilecek map adi, ornek: metin2_map_a1",
    )
    analyze_raw_sectree_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    analyze_raw_sectree_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "raw_sectree_block_report.json"),
        help="Yazilacak raw sectree block raporu yolu",
    )
    analyze_raw_sectree_parser.add_argument(
        "--sample-block-limit",
        type=int,
        default=4,
        help="Raporlanacak ilk raw block sayisi",
    )
    analyze_raw_sectree_parser.add_argument(
        "--sample-dword-limit",
        type=int,
        default=16,
        help="Her block icin yazilacak ilk DWORD sayisi",
    )

    analyze_raw_sectree_batch_parser = subparsers.add_parser(
        "analyze-raw-sectree-packer-batch",
        help="Tum mapler icin raw sectree block toplu ozeti uret",
    )
    analyze_raw_sectree_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    analyze_raw_sectree_batch_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    analyze_raw_sectree_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "raw_sectree_block_batch.json"),
        help="Yazilacak toplu raw sectree block raporu yolu",
    )

    export_server_attr_parser = subparsers.add_parser(
        "export-server-attr",
        help="Tek map icin ilk gercek server_attr dosyasini uret",
    )
    export_server_attr_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    export_server_attr_parser.add_argument(
        "--map-name",
        required=True,
        help="Export edilecek map adi, ornek: metin2_map_a1",
    )
    export_server_attr_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    export_server_attr_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "exported_server_attr"),
        help="Yazilacak server_attr dosyasi yolu",
    )
    export_server_attr_parser.add_argument(
        "--report-file",
        default=str(Path.cwd() / "analysis" / "exported_server_attr_report.json"),
        help="Yazilacak export raporu yolu",
    )
    export_server_attr_parser.add_argument(
        "--mapping-profile",
        default="exe_compat_v2",
        choices=sorted(list_mapping_profiles().keys()),
        help="Kullanilacak attr -> DWORD mapping profili",
    )

    export_server_attr_batch_parser = subparsers.add_parser(
        "export-server-attr-batch",
        help="Tum mapler icin server_attr dosyalarini toplu uret",
    )
    export_server_attr_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    export_server_attr_batch_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    export_server_attr_batch_parser.add_argument(
        "--output-root",
        default=str(Path.cwd() / "exported_server_attrs"),
        help="Toplu export kok klasoru",
    )
    export_server_attr_batch_parser.add_argument(
        "--report-file",
        default=str(Path.cwd() / "analysis" / "exported_server_attr_batch.json"),
        help="Yazilacak toplu export raporu yolu",
    )
    export_server_attr_batch_parser.add_argument(
        "--mapping-profile",
        default="exe_compat_v2",
        choices=sorted(list_mapping_profiles().keys()),
        help="Kullanilacak attr -> DWORD mapping profili",
    )

    diff_server_attr_parser = subparsers.add_parser(
        "diff-server-attr-blocks",
        help="Ornek server_attr ile uretilen ham DWORD bloklarini karsilastir",
    )
    diff_server_attr_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    diff_server_attr_parser.add_argument(
        "--map-name",
        required=True,
        help="Karsilastirilacak map adi, ornek: metin2_map_a1",
    )
    diff_server_attr_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    diff_server_attr_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "server_attr_block_diff.json"),
        help="Yazilacak block diff raporu yolu",
    )
    diff_server_attr_parser.add_argument(
        "--mapping-profile",
        default="exe_compat_v2",
        choices=sorted(list_mapping_profiles().keys()),
        help="Kullanilacak attr -> DWORD mapping profili",
    )
    diff_server_attr_parser.add_argument(
        "--block-limit",
        type=int,
        default=8,
        help="Karsilastirilacak ilk block sayisi",
    )

    diff_server_attr_batch_parser = subparsers.add_parser(
        "diff-server-attr-blocks-batch",
        help="Ornek server_attr bulunan maplerde toplu block diff ozeti uret",
    )
    diff_server_attr_batch_parser.add_argument(
        "--source-root",
        default=r"D:\ymir work",
        help="Client map klasorlerinin bulundugu ana dizin",
    )
    diff_server_attr_batch_parser.add_argument(
        "--sample-root",
        default=str(Path.cwd() / "output ornekleri"),
        help="Ornek server_attr klasorlerinin bulundugu dizin",
    )
    diff_server_attr_batch_parser.add_argument(
        "--output-file",
        default=str(Path.cwd() / "analysis" / "server_attr_block_diff_batch.json"),
        help="Yazilacak toplu block diff raporu yolu",
    )
    diff_server_attr_batch_parser.add_argument(
        "--mapping-profile",
        default="exe_compat_v2",
        choices=sorted(list_mapping_profiles().keys()),
        help="Kullanilacak attr -> DWORD mapping profili",
    )
    diff_server_attr_batch_parser.add_argument(
        "--block-limit",
        type=int,
        default=8,
        help="Her map icin karsilastirilacak ilk block sayisi",
    )
    return parser


def _collect_requested_map_names(
    cli_map_names: list[str],
    map_list_file: str | None,
) -> list[str]:
    requested: list[str] = []
    for map_name in cli_map_names:
        normalized = map_name.strip()
        if normalized and normalized not in requested:
            requested.append(normalized)

    if map_list_file:
        list_path = Path(map_list_file)
        for raw_line in list_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in requested:
                requested.append(line)

    return requested


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "parse-setting":
        setting = parse_setting_file(args.setting_file)
        print(json.dumps(asdict(setting), indent=2, ensure_ascii=True))
        return 0

    if args.command == "scan-maps":
        map_sources = discover_map_sources(args.source_root)
        results = generate_bulk_outputs(
            map_sources,
            args.output_root,
            sample_root=args.sample_root,
        )
        response = {
            "source_root": args.source_root,
            "output_root": args.output_root,
            "sample_root": args.sample_root,
            "map_count": len(map_sources),
            "maps": [
                {
                    "name": map_source.name,
                    "area_directory_count": len(map_source.area_directories),
                    "attr_file_count": len(map_source.attr_files),
                }
                for map_source in map_sources
            ],
            "results": [
                {
                    "map_name": result.map_name,
                    "output_path": str(result.output_path),
                    "files_written": result.files_written,
                    "warnings": result.warnings,
                }
                for result in results
            ],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "generate-maps":
        requested_map_names = _collect_requested_map_names(
            args.map_name,
            args.map_list_file,
        )
        if not requested_map_names:
            raise SystemExit("En az bir map adi verilmeli: --map-name veya --map-list-file")
        workflow = run_selected_generation(
            source_root=args.source_root,
            output_root=args.output_root,
            requested_map_names=requested_map_names,
            sample_root=args.sample_root,
            report_file=args.report_file,
        )
        summary = workflow.summary
        response = {
            "source_root": args.source_root,
            "output_root": args.output_root,
            "sample_root": args.sample_root,
            "report_path": str(workflow.report_path),
            "requested_map_count": summary["requested_map_count"],
            "generated_map_count": summary["generated_map_count"],
            "missing_requested_map_count": summary["missing_requested_map_count"],
            "server_attr_status_counts": summary["server_attr_status_counts"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "launch-gui":
        run_gui()
        return 0

    if args.command == "analyze-server-attr":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        sample_path = find_matching_server_attr_sample(
            args.map_name,
            args.sample_root,
        )
        report_path = write_attr_analysis_report(
            selected,
            args.output_file,
            sample_path,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
            "sample_path": str(sample_path) if sample_path else None,
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-server-attr-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_attr_summary(
            map_sources,
            args.sample_root,
            args.output_file,
        )
        summary = build_batch_attr_summary(map_sources, args.sample_root)
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-attr-family":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_attr_family_report(selected, args.output_file)
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-attr-family-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_attr_family_summary(map_sources, args.output_file)
        response = {
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-dword-candidates":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        map_sources = discover_map_sources(args.source_root)
        batch_summary = build_batch_attr_family_summary(map_sources)
        report_path = write_attr_dword_candidate_report(
            selected,
            args.output_file,
            batch_summary,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-dword-candidates-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_attr_dword_candidate_summary(
            map_sources,
            args.output_file,
        )
        summary = build_batch_attr_dword_candidate_summary(map_sources)
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-dword-matrix-preview":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_attr_dword_matrix_preview(
            selected,
            args.output_file,
            args.preview_width,
            args.preview_height,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-dword-matrix-preview-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_attr_dword_matrix_preview_summary(
            map_sources,
            args.output_file,
        )
        summary = build_batch_attr_dword_matrix_preview_summary(map_sources)
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-sectree-block-preview":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_sectree_block_preview(
            selected,
            args.output_file,
            sample_block_limit=args.sample_block_limit,
            sample_rows=args.sample_rows,
            sample_cols=args.sample_cols,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-sectree-block-preview-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_sectree_block_preview_summary(
            map_sources,
            args.output_file,
        )
        summary = build_batch_sectree_block_preview_summary(map_sources)
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-raw-sectree-packer":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_raw_sectree_block_report(
            selected,
            args.output_file,
            sample_block_limit=args.sample_block_limit,
            sample_dword_limit=args.sample_dword_limit,
            sample_root=args.sample_root,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "analyze-raw-sectree-packer-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_raw_sectree_block_summary(
            map_sources,
            args.output_file,
            sample_root=args.sample_root,
        )
        summary = build_batch_raw_sectree_block_summary(
            map_sources,
            sample_root=args.sample_root,
        )
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "export-server-attr":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_server_attr_export_report(
            selected,
            output_file=args.output_file,
            report_file=args.report_file,
            sample_root=args.sample_root,
            mapping_profile=args.mapping_profile,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
            "output_file": args.output_file,
            "lzo_backend_available": is_lzo_backend_available(),
            "mapping_profile": args.mapping_profile,
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "export-server-attr-batch":
        map_sources = discover_map_sources(args.source_root)
        summary = export_server_attr_batch(
            map_sources,
            output_root=args.output_root,
            sample_root=args.sample_root,
            mapping_profile=args.mapping_profile,
        )
        report_path = write_server_attr_batch_summary(
            map_sources,
            output_root=args.output_root,
            report_file=args.report_file,
            sample_root=args.sample_root,
            summary=summary,
            mapping_profile=args.mapping_profile,
        )
        response = {
            "report_path": str(report_path),
            "output_root": args.output_root,
            "map_count": summary["map_count"],
            "lzo_backend_available": is_lzo_backend_available(),
            "mapping_profile": args.mapping_profile,
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "diff-server-attr-blocks":
        selected = resolve_map_source_by_name(args.source_root, args.map_name)
        if selected is None:
            raise SystemExit(f"Map bulunamadi: {args.map_name}")

        report_path = write_server_attr_block_diff_report(
            selected,
            sample_root=args.sample_root,
            output_file=args.output_file,
            mapping_profile=args.mapping_profile,
            block_limit=args.block_limit,
        )
        response = {
            "map_name": selected.name,
            "report_path": str(report_path),
            "mapping_profile": args.mapping_profile,
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    if args.command == "diff-server-attr-blocks-batch":
        map_sources = discover_map_sources(args.source_root)
        report_path = write_batch_server_attr_block_diff_summary(
            map_sources,
            sample_root=args.sample_root,
            output_file=args.output_file,
            mapping_profile=args.mapping_profile,
            block_limit=args.block_limit,
        )
        summary = build_batch_server_attr_block_diff_summary(
            map_sources,
            sample_root=args.sample_root,
            mapping_profile=args.mapping_profile,
            block_limit=args.block_limit,
        )
        response = {
            "report_path": str(report_path),
            "map_count": summary["map_count"],
            "fully_matching_map_count": summary["fully_matching_map_count"],
            "total_mismatch_count": summary["total_mismatch_count"],
            "mapping_profile": args.mapping_profile,
        }
        print(json.dumps(response, indent=2, ensure_ascii=True))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
