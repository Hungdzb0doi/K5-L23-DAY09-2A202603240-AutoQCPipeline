"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07:
  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    reviewed = set(reviewed or ())
    stems_set = set(image_stems)
    n_images = len(image_stems)

    # 1. Đếm lỗi bắt buộc (ERROR) - không bao giờ được bỏ qua kể cả ảnh đã duyệt
    errors = [i for i in issues if i.severity == ERROR]
    n_errors = len(errors)

    # 2. Đếm số ảnh có cảnh báo (WARN) trong image_stems, chưa được người duyệt
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stems_set and i.image not in reviewed
    }
    n_warn_images = len(warn_images)

    # 3. Tính tỉ lệ ảnh có cảnh báo
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0

    # 4. Ngưỡng Hold từ config
    warn_ratio_hold = cfg.get("gate", {}).get("warn_ratio_hold", 0.10)

    reasons = []
    if n_errors > 0:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (severity ERROR) cần sửa")
    elif warn_ratio >= warn_ratio_hold:
        decision = "Hold"
        reasons.append(
            f"Tỉ lệ ảnh có cảnh báo {warn_ratio:.2%} ({n_warn_images}/{n_images} ảnh) >= ngưỡng Hold {warn_ratio_hold:.2%}"
        )
    else:
        decision = "Release"
        reasons.append(
            f"Đạt điều kiện Release: 0 lỗi bắt buộc, tỉ lệ cảnh báo {warn_ratio:.2%} ({n_warn_images}/{n_images} ảnh) < ngưỡng Hold {warn_ratio_hold:.2%}"
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
