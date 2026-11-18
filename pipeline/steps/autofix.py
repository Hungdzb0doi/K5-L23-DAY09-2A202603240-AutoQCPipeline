"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q
"""
from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line

REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}


def fix(ds, issues, cfg):
    # Chỉ xử lý các lỗi có severity ERROR, bỏ qua WARN
    error_issues = [i for i in issues if i.severity == ERROR]
    if not error_issues:
        return []

    fixes = []

    # 1. Phát hiện các ảnh cần xoá (DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE)
    images_to_remove = set()
    for i in error_issues:
        if i.code in REMOVE_IMAGE_CODES or i.code.startswith("DUP_IMAGE"):
            images_to_remove.add(i.image)

    for stem in sorted(images_to_remove):
        img_p = ds.image_path(stem)
        before_str = f"image: {img_p.name}" if img_p else f"image: {stem}"
        if img_p and img_p.exists():
            try:
                img_p.unlink()
            except Exception:
                pass

        lbl_p = ds.label_path(stem)
        if lbl_p and lbl_p.exists():
            try:
                lbl_p.unlink()
            except Exception:
                pass

        ds._size_cache.pop(stem, None)
        fixes.append({
            "image": stem,
            "line": None,
            "action": "remove_image",
            "before": before_str,
            "after": "(đã xoá)",
        })

    # 2. Xử lý BAD_CLASS_NAME (sửa data.yaml)
    has_bad_class_name = any(i.code == "BAD_CLASS_NAME" for i in error_issues)
    if has_bad_class_name and ds.yaml_path.exists():
        try:
            d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            d = {}
        before_names = str(d.get("names", ""))
        d["names"] = list(cfg.get("classes", []))
        ds.yaml_path.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": None,
            "action": "rename_classes",
            "before": before_names,
            "after": str(cfg.get("classes", [])),
        })

    # 3. Xử lý MISSING_LABEL_FILE (không tạo file, ghi needs_label)
    missing_label_stems = sorted({
        i.image for i in error_issues
        if i.code == "MISSING_LABEL_FILE" and i.image not in images_to_remove
    })
    for stem in missing_label_stems:
        fixes.append({
            "image": stem,
            "line": None,
            "action": "needs_label",
            "before": "(không có file)",
            "after": "chuyển người gán",
        })

    # 4. Xử lý các lỗi dòng trong file nhãn
    # Gom lỗi theo stem (chỉ những ảnh không bị xoá và có số dòng)
    line_issues_by_stem = defaultdict(list)
    for i in error_issues:
        if i.image in images_to_remove or i.image in ("data.yaml", "<dataset>"):
            continue
        if i.line is not None:
            line_issues_by_stem[i.image].append(i)

    for stem in sorted(line_issues_by_stem.keys()):
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue

        orig_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        issues_for_stem = line_issues_by_stem[stem]

        # Gom issue theo số dòng (1-based)
        by_line = defaultdict(list)
        for iss in issues_for_stem:
            by_line[iss.line].append(iss)

        new_lines = []
        file_fixes = []

        for line_idx in range(1, len(orig_lines) + 1):
            raw_text = orig_lines[line_idx - 1]
            if line_idx not in by_line:
                new_lines.append(raw_text)
                continue

            current_issues = by_line[line_idx]
            codes = {iss.code for iss in current_issues}

            # Nếu có bất kỳ mã nào trong DROP_LINE_CODES -> drop_line thắng
            must_drop = bool(codes & DROP_LINE_CODES)

            if not must_drop and "BOX_OUT_OF_IMAGE" in codes:
                # Thử clip box về [0, 1]
                try:
                    c, cx, cy, w, h = parse_yolo_line(raw_text)
                    x1 = cx - w / 2.0
                    x2 = cx + w / 2.0
                    y1 = cy - h / 2.0
                    y2 = cy + h / 2.0

                    x1_c = max(0.0, min(1.0, x1))
                    x2_c = max(0.0, min(1.0, x2))
                    y1_c = max(0.0, min(1.0, y1))
                    y2_c = max(0.0, min(1.0, y2))

                    w_c = x2_c - x1_c
                    h_c = y2_c - y1_c

                    if w_c <= 1e-7 or h_c <= 1e-7:
                        must_drop = True
                    else:
                        cx_c = (x1_c + x2_c) / 2.0
                        cy_c = (y1_c + y2_c) / 2.0
                        clipped_line = f"{int(c)} {round(cx_c, 6)} {round(cy_c, 6)} {round(w_c, 6)} {round(h_c, 6)}"
                        new_lines.append(clipped_line)
                        file_fixes.append({
                            "image": stem,
                            "line": line_idx,
                            "action": "clip_box",
                            "before": raw_text,
                            "after": clipped_line,
                        })
                except Exception:
                    must_drop = True

            if must_drop:
                file_fixes.append({
                    "image": stem,
                    "line": line_idx,
                    "action": "drop_line",
                    "before": raw_text,
                    "after": "(đã xoá)",
                })

        # Ghi lại nội dung file nhãn
        if new_lines:
            lbl_p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        else:
            lbl_p.write_text("", encoding="utf-8")

        fixes.extend(file_fixes)

    return fixes
