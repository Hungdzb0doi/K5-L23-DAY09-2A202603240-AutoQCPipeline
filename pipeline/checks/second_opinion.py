"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg.get("second_opinion", {})
    conf_thresh = so_cfg.get("conf", 0.25)
    min_area_px = so_cfg.get("min_area_px", 600)
    fp_conf = so_cfg.get("fp_conf", 0.1)
    iou_missing = so_cfg.get("iou_missing", 0.3)
    iou_match = so_cfg.get("iou_match", 0.5)
    iou_loose = so_cfg.get("iou_loose", 0.5)
    num_classes = len(ds.classes)

    issues = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue
        if not ds.label_path(stem).exists():
            continue

        im_size = ds.image_size(stem)
        if not im_size:
            continue
        W, H = im_size

        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        # Lọc các dòng nhãn hợp lệ kèm số dòng
        valid_labels = []
        for line_no, text in raw_lines:
            try:
                b = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= b[0] < num_classes:
                valid_labels.append((line_no, b))

        all_preds = preds.get(stem, [])

        # 1. Tập dự đoán P thoả mãn conf >= conf VÀ diện tích px >= min_area_px
        P = []
        for r in all_preds:
            p_cls, p_conf, p_cx, p_cy, p_w, p_h = r
            area_px = (p_w * W) * (p_h * H)
            if p_conf >= conf_thresh and area_px >= min_area_px:
                P.append(r)

        # Duyệt từng dự đoán r trong P
        for r in P:
            r_cls, r_conf, r_cx, r_cy, r_w, r_h = r
            r_box = (r_cx, r_cy, r_w, r_h)

            # Tìm cands: nhãn có IoU >= iou_missing
            cands = []
            for line_no, b in valid_labels:
                lbl_cls = b[0]
                lbl_box = (b[1], b[2], b[3], b[4])
                iou = iou_xywh(r_box, lbl_box)
                if iou >= iou_missing:
                    cands.append((lbl_cls, iou))

            if not cands:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_MISSING",
                    stem,
                    f"model phát hiện {ds.classes[r_cls]} (conf {r_conf:.2f}) nhưng không có nhãn",
                    line=None,
                    extra={"conf": r_conf, "class": r_cls},
                ))
            else:
                same_class = [iou for lbl_cls, iou in cands if lbl_cls == r_cls]
                if same_class:
                    best_same = max(same_class)
                    if best_same < iou_loose:
                        issues.append(Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box nhãn lỏng/lệch so với model (IoU {best_same:.2f} < {iou_loose})",
                            line=None,
                            extra={"conf": r_conf, "iou": best_same},
                        ))
                    else:
                        pass  # Đúng lớp phủ vật này, không cờ gì
                else:
                    diff_class = [iou for lbl_cls, iou in cands if lbl_cls != r_cls]
                    if diff_class and max(diff_class) >= iou_match:
                        best_diff = max(diff_class)
                        issues.append(Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"nghi gán nhầm lớp: model dự đoán {ds.classes[r_cls]} (conf {r_conf:.2f})",
                            line=None,
                            extra={"conf": r_conf, "iou": best_diff},
                        ))
                    else:
                        pass  # Mơ hồ, không cờ gì

        # 2. Kiểm tra POSSIBLE_FALSE_POS cho từng dòng nhãn hợp lệ
        # So với các dự đoán có conf >= fp_conf (không lọc diện tích)
        fp_preds = [r for r in all_preds if r[1] >= fp_conf]
        for line_no, b in valid_labels:
            lbl_cls = b[0]
            lbl_box = (b[1], b[2], b[3], b[4])
            has_match = any(
                iou_xywh(lbl_box, (r[2], r[3], r[4], r[5])) >= iou_missing
                for r in fp_preds
            )
            if not has_match:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_FALSE_POS",
                    stem,
                    f"box nhãn không khớp dự đoán nào của model (conf >= {fp_conf})",
                    line=line_no,
                    extra={"class": lbl_cls},
                ))

    return issues
