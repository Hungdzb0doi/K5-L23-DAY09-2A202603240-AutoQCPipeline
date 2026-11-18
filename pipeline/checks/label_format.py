"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    lf_cfg = cfg.get("label_format", {})
    overflow_tol = lf_cfg.get("overflow_tol", 0.002)
    min_box_px = lf_cfg.get("min_box_px", 12)
    max_box_frac = lf_cfg.get("max_box_frac", 0.95)
    dup_box_iou = lf_cfg.get("dup_box_iou", 0.9)
    num_classes = len(ds.classes)

    issues = []
    for lp in ds.label_files():
        stem = lp.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue
        im_size = ds.image_size(stem)
        prev_boxes = []  # list of (class_id, cx, cy, w, h)

        for line_no, text in lines:
            # 1. Parse dòng
            try:
                b = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"dòng nhãn sai định dạng: {e}", line=line_no))
                continue

            c, cx, cy, w, h = b

            # 2. Kiểm tra ID lớp
            if c < 0 or c >= num_classes:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài khoảng [0, {num_classes - 1}]", line=line_no))
                continue

            # 3. Kiểm tra box kích thước <= 0
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"kích thước box không hợp lệ (w={w}, h={h})", line=line_no))
                continue

            # 4. Kiểm tra tràn ảnh
            x1 = cx - w / 2
            x2 = cx + w / 2
            y1 = cy - h / 2
            y2 = cy + h / 2
            overflow = max(0.0, -x1, x2 - 1.0, -y1, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh (mức tràn {overflow:.4f} > tol {overflow_tol})", line=line_no, extra={"overflow": overflow}))

            # 5. Kiểm tra trùng lặp box (cùng lớp, IoU > dup_box_iou)
            for p_c, p_cx, p_cy, p_w, p_h in prev_boxes:
                if p_c == c and iou_xywh((cx, cy, w, h), (p_cx, p_cy, p_w, p_h)) > dup_box_iou:
                    issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, f"box trùng với một box trước đó cùng lớp (IoU > {dup_box_iou})", line=line_no))
                    break

            # 6. Kiểm tra box quá nhỏ (cạnh ngắn < min_box_px)
            if im_size:
                w_px = w * im_size[0]
                h_px = h * im_size[1]
                short_px = min(w_px, h_px)
                if short_px < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem, f"cạnh ngắn box {short_px:.1f}px < {min_box_px}px", line=line_no))

            # 7. Kiểm tra box quá lớn (diện tích > max_box_frac)
            if w * h > max_box_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, f"diện tích box {w * h:.2f} > {max_box_frac}", line=line_no))

            prev_boxes.append((c, cx, cy, w, h))

    return issues
