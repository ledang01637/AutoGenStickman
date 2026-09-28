# STICKMAN BIOMECHANICS — Quy tắc sinh học bắt buộc

> Tài liệu tham chiếu khi viết bất kỳ pose mới nào.
> Vi phạm bất kỳ quy tắc nào = animation trông sai ngay lập tức.

---

## 1. Hệ tọa độ & Bone lengths

```
Gốc (0, 0) = hip
+x = phải, +y = lên
Đơn vị = char_scale

L_THIGH  = 0.45   # đùi
L_CALF   = 0.47   # cẳng chân
L_ARM    = 0.35   # cánh tay trên
L_FOREARM= 0.32   # cẳng tay

TORSO_LEN = 0.62  # hip → shoulder (bất biến)
HEAD_OFF  = 0.46  # shoulder → tâm đầu

Foot ở y = -0.92 khi đứng thẳng (= -L_THIGH - L_CALF)
```

---

## 2. Vai — bất biến so với hông

**Quy tắc:** `sh_y = hip_y + TORSO_LEN` — luôn luôn, mọi pose.

Khi hông hạ (ngồi), vai hạ theo đúng `TORSO_LEN`. Không bao giờ hardcode `sh_y` cố định khi `hip_y` thay đổi.

```python
# Đúng
hip_y = -0.30
sh = (0, hip_y + TORSO_LEN)   # = (0, 0.32)

# Sai
sh = (0, 0.62)   # ← hip đã hạ xuống -0.30 nhưng vai vẫn ở 0.62
```

---

## 3. Khuỷu tay — luôn chỉ xuống

**Quy tắc:** khuỷu tay KHÔNG BAO GIỜ cao hơn vai khi tay đưa lên.

```
Sai:  vai ──→ khuỷu (ngang/lên) ──→ tay (lên miệng)
Đúng: vai ──→ khuỷu (xuống)     ──→ tay (lên miệng)
```

**Áp dụng:** Bất kỳ khi nào tay đưa lên (ăn, uống, vẫy, che mặt) → dùng IK, chọn solution có `elbow_y` thấp nhất.

```python
def _arm_ik(sh_x, sh_y, hx, hy, side):
    # Tính 2 solutions từ định lý cosin
    ea1 = theta + alpha
    ea2 = theta - alpha
    ey1 = sh_y + L_ARM * math.sin(ea1)
    ey2 = sh_y + L_ARM * math.sin(ea2)
    # Luôn chọn solution thấp hơn
    ea = ea1 if ey1 < ey2 else ea2
```

**Ngoại lệ:**
- **Tay dang ngang hoàn toàn** (shrug, point_right) — khuỷu có thể ngang vai.
- **Chugging / dốc ngược** (uống cạn dốc đáy cốc lên trời, ném đồ vật qua đầu) — bàn tay phải vươn lên cao hơn đầu, khuỷu tay được phép nâng lên ngang hoặc vượt trục vai một chút. Trong trường hợp này, **chọn IK solution có `elbow_y` cao hơn** để tránh cánh tay trông gãy gượng ép.

```python
# Chugging: target hand_y > sh_y + 0.3 → cho phép elbow lên
if hand_y > sh_y + 0.3:   # ngưỡng "dốc ngược"
    ea = ea1 if ey1 > ey2 else ea2   # chọn solution CAO hơn
else:
    ea = ea1 if ey1 < ey2 else ea2   # mặc định: chọn solution thấp hơn
```

---

## 4. Gối — chỉ gập 1 chiều

**Quy tắc:** gối không bao giờ gập về phía trước (hyperextension). Chỉ gập về phía sau.

```python
# Đúng — anatomical constraint
ak = -1.0 * max(0.0, -math.cos(w))   # chỉ âm hoặc 0

# Sai
ak = -1.0 * math.cos(w)   # có thể dương = gối gập về trước
```

`ang_k` (góc gối bổ sung) LUÔN âm hoặc 0 trong `_leg()`.

---

## 5. Tay-chân khi đi/chạy — ngược pha bắt buộc

**Quy tắc:** chân phải ra trước → tay trái ra trước. Không bao giờ cùng bên ra cùng lúc.

```python
# Đúng
as_l = +0.50 * math.sin(w)          # tay trái
as_r = +0.50 * math.sin(w + math.pi)  # tay phải = ngược pha

ah_r = -0.70 * math.sin(w)          # chân phải
ah_l = -0.70 * math.sin(w + math.pi)  # chân trái = ngược pha

# Tay ngược pha chân cùng bên:
# as_l cùng pha ah_r (trái↔phải)
# as_r cùng pha ah_l (phải↔trái)
```

---

## 6. Khuỷu gập khi swing — không phải lúc nào cũng gập

**Quy tắc:** khuỷu chỉ gập khi tay đang đưa về phía trước. Khi tay ra sau, cánh tay duỗi thẳng.

```python
# Đúng
ae_l = 0.55 * max(0.0, math.sin(w))   # chỉ gập khi sin > 0

# Sai
ae_l = 0.55 * math.sin(w)   # gập cả 2 chiều
```

---

## 7. Bob & Sway — tần số và biên độ

| Biến | Tần số | Biên độ | Lý do |
|------|--------|---------|-------|
| `bob` (lên xuống) | `2×` tần số bước | 0.018–0.030 | 2 heel strike/bước |
| `sway` (lắc hông) | `1×` tần số bước | 0.010–0.015 | trọng tâm dịch chuyển |

**Giảm dần lên trên:**
```python
hip.x      = sway           # 100%
shoulder.x = sway * 0.5     # 50%
head.x     = sway * 0.3     # 30%
```

---

## 8. Tư thế ngồi — góc đùi/cẳng chân

| Tư thế | ang_h (đùi) | ang_k (gối) |
|--------|-------------|-------------|
| Đứng thẳng | 0 | 0 |
| Ngồi ghế | ~π/2 (nằm ngang) | ~-π/2 (thả xuống) |
| Ngồi bệt | ~π/2 (chĩa trước) | ~-2.4 (gập sát) |
| Chồm hổm | tọa độ trực tiếp | tọa độ trực tiếp |

**Khi ngồi:** `hip_y` âm (hông hạ xuống), `sh_y = hip_y + TORSO_LEN` tự điều chỉnh.

---

## 9. FK vs IK — khi nào dùng cái nào

| Tình huống | Dùng | Lý do |
|------------|------|-------|
| Tay thả lỏng, swing đi bộ | FK (`_arm`) | góc tự nhiên, không cần precision |
| Tay đưa lên miệng/mặt | IK | cần khuỷu chỉ xuống chính xác |
| Tay cầm vật ở vị trí cố định | IK | target rõ ràng, FK sẽ sai hướng |
| Tay dang ngang (shrug) | FK | không có constraint khuỷu |

---

## 10. Front-view vs Side-view

### Side-view (background nhìn ngang: office, bedroom, city_day...)
- Tay swing theo trục X (trước/sau)
- `_arm` FK: `ang_s` dương = tay ra trước (+x)
- IK: target `hx` theo hướng di chuyển

### Front-view (background nhìn thẳng: street_food, cafe, gym...)
- Tay dang ra theo trục X (trái/phải)
- Vai thực tế dãn rộng: `real_sh_x = sh_x ± 0.16`

**Khi tương tác với mặt/ngực (ăn, uống, lau mặt):**
Miệng và mặt nằm tại trục trung tâm (`x ≈ 0.0`). Tay phải đang ở vai `x = +0.16` phải **đi chéo vào trong** để đưa thức ăn/vật vào miệng — đây là **cross-body movement** hoàn toàn tự nhiên. Do đó:

- **Không** áp dụng quy tắc `hand_x ≥ real_sh_x` cho tương tác mặt/ngực.
- `hand_x` tiến về `0.0` (hoặc âm nhẹ nếu cần).
- Khuỷu tay sẽ tự động **bẻ ra ngoài (flare out)** — IK chọn solution đẩy khuỷu ra xa trục thân để tránh xuyên qua lồng ngực.

```python
# Front-view: tay phải đưa thức ăn lên miệng
real_sh_x = 0.16          # vai phải
hand_x    = 0.0           # miệng ở trung tâm → cross-body
hand_y    = sh_y + 0.25   # ngang miệng

# IK tự bẻ khuỷu ra ngoài (+x) để tránh xuyên ngực
# → real_sh_x ≥ elbow_x là dấu hiệu đúng
```

**Khi tay dang ra hai bên (vẫy tay, shrug, chỉ tay):**
`hand_x` vẫn phải `≥ real_sh_x` về phía side tương ứng — quy tắc cũ áp dụng bình thường.

---

## 11. Checklist trước khi thêm pose mới

```
[ ] sh_y = hip_y + TORSO_LEN (không hardcode khi hip_y ≠ 0)
[ ] ang_k (gối) luôn âm hoặc 0
[ ] Tay đưa lên → dùng IK, chọn elbow_y thấp nhất
    (ngoại lệ: chugging/ném → chọn elbow_y cao hơn khi hand_y > sh_y + 0.3)
[ ] Walk/run: as_l và as_r ngược pha nhau (± π)
[ ] Walk/run: tay ngược pha chân cùng bên
[ ] ae (khuỷu) dùng max(0, ...) — không gập khi tay ra sau
[ ] Bob tần số 2× bước, sway tần số 1× bước
[ ] Sway giảm dần: hip 100% → shoulder 50% → head 30%
[ ] Front-view tương tác mặt/ngực: hand_x → 0.0 (cross-body), KHÔNG dùng hand_x ≥ real_sh_x
[ ] Front-view tay dang ngang: hand_x ≥ real_sh_x về phía side tương ứng
[ ] Kiểm tra t=0 (tư thế bắt đầu trông tự nhiên không)
```

---

## 12. Các lỗi phổ biến & cách nhận biết

| Lỗi trông thấy | Nguyên nhân | Fix |
|----------------|-------------|-----|
| Khuỷu đẩy sang ngang khi tay lên miệng | FK với ang_s lớn | Đổi sang IK |
| 2 tay cùng chiều khi đi | as_l, as_r cùng pha | Thêm `+ math.pi` vào 1 bên |
| Gối gập về trước | ang_k dương | Dùng `max(0, ...)` |
| Vai không hạ khi ngồi | sh_y hardcode | `sh_y = hip_y + TORSO_LEN` |
| Khuỷu lên cao hơn vai (uống thường) | IK chọn sai solution | Chọn solution `ey` thấp hơn |
| Cánh tay gãy gượng khi chugging | IK ép elbow xuống quá | Chọn solution `ey` cao hơn khi `hand_y > sh_y + 0.3` |
| Tay cùng bên với chân ra trước | phase lỗi | `as_r = sin(w + π)` |
| Nhân vật nổi trên mặt đất | foot_y sai | `foot_y = hip_y - L_THIGH - L_CALF` |
| Tay phải không chạm miệng ở front-view | hand_x = 0.16 (sai) | hand_x → 0.0, dùng cross-body movement |