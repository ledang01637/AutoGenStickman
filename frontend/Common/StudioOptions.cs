// frontend/Common/StudioOptions.cs
namespace frontend.Common;

public sealed record PaceOption(
    string Value,
    string Label,
    string ShortDesc,
    string Detail,
    bool IsFastCut = false
);

public sealed record StoryStructureOption(
    string Value,
    string Label,
    string ShortDesc,
    string Detail
);

public sealed record ToneOption(
    string Value,
    string Label,
    string Emoji,
    string ShortDesc
);

public sealed record VoiceOption(
    string Value,
    string Label,
    string Emoji
);

public sealed record RatioOption(
    string Value,
    string Label,
    string Emoji
);

public static class StudioOptions
{
    public static readonly List<PaceOption> Paces =
    [
        new(
            Value:     "storytelling",
            Label:     "📖 Kể chuyện",
            ShortDesc: "7–9 giây mỗi cảnh",
            Detail:    "Dành cho câu chuyện lịch sử, phim tài liệu, tiểu sử"
        ),
        new(
            Value:     "balanced",
            Label:     "⚖️ Cân bằng",
            ShortDesc: "5–7 giây mỗi cảnh",
            Detail:    "Phù hợp cho nội dung giáo dục, hướng dẫn, kể chuyện thường ngày"
        ),
        new(
            Value:     "dynamic",
            Label:     "⚡ Năng động",
            ShortDesc: "4–5 giây mỗi cảnh",
            Detail:    "Hợp với tin tức, bảng xếp hạng, nội dung trending"
        ),
        new(
            Value:     "cinematic",
            Label:     "🎬 Điện ảnh",
            ShortDesc: "9–12 giây mỗi cảnh",
            Detail:    "Kể chuyện lắng đọng, cảm xúc sâu — cần nhịp chậm để thấm"
        ),
        new(
            Value:     "fast_cut",
            Label:     "🔥 Siêu tốc",
            ShortDesc: "2–3 giây mỗi cảnh",
            Detail:    "Meme, drama, tin nóng — nhịp cực nhanh giữ attention Gen Z",
            IsFastCut: true
        ),
    ];

    public static readonly List<StoryStructureOption> StoryStructures =
    [
        // ── General ──────────────────────────────────────────────────────────
        new(
            Value:     "hook_twist",
            Label:     "🎣 Mở đầu gây sốc, kết bất ngờ",
            ShortDesc: "Hook → Dẫn dắt → Twist → Cú kết đắt",
            Detail:    "Câu đầu tiên kéo người xem ở lại, twist cuối khiến họ chia sẻ ngay"
        ),
        new(
            Value:     "problem_solve",
            Label:     "🔧 Vạch trần vấn đề & đưa giải pháp",
            ShortDesc: "Vấn đề sốc → Gốc rễ → Hậu quả thật → Cách khắc phục",
            Detail:    "Nêu vấn đề ai cũng gặp nhưng chưa ai giải thích được, rồi đưa ra lối thoát"
        ),
        new(
            Value:     "timeline",
            Label:     "📅 Kể lại sự kiện theo trình tự",
            ShortDesc: "Trước khi xảy ra → Đỉnh điểm → Hậu quả → Ngày nay",
            Detail:    "Phù hợp lịch sử, sự kiện có thật, scandal — kéo người xem qua từng mốc thời gian"
        ),
        new(
            Value:     "debate",
            Label:     "⚔️ Tranh luận 2 chiều, phán quyết cuối",
            ShortDesc: "Quan điểm A → Quan điểm B → Kết luận",
            Detail:    "Trình bày cả hai phía công bằng, kết bằng verdict của bạn — dễ gây tranh luận bình luận"
        ),

        // ── Narrative ────────────────────────────────────────────────────────
        new(
            Value:     "hero_journey",
            Label:     "🦸 Từ tay trắng đến đỉnh cao",
            ShortDesc: "Cuộc sống thường → Biến cố → Vượt khó → Bài học",
            Detail:    "Kể hành trình một con người thật vượt qua nghịch cảnh — truyền cảm hứng mạnh"
        ),
        new(
            Value:     "rags_to_riches",
            Label:     "💰 Khởi nghiệp từ con số 0",
            ShortDesc: "Xuất phát điểm khó → Quyết định thay đổi → Bước ngoặt → Thành công",
            Detail:    "Câu chuyện lột xác tài chính hoặc sự nghiệp — phù hợp nhân vật có thật"
        ),
        new(
            Value:     "fall_from_grace",
            Label:     "📉 Từ đỉnh cao đến vực thẳm",
            ShortDesc: "Vinh quang → Vết nứt → Sụp đổ → Nguyên nhân thật",
            Detail:    "Phân tích tại sao người/công ty thành công lại thất bại — hấp dẫn và có chiều sâu"
        ),
        new(
            Value:     "mystery_reveal",
            Label:     "🔍 Bí ẩn dần hé lộ",
            ShortDesc: "Câu hỏi bí ẩn → Manh mối → Lý thuyết sai → Sự thật gây sốc",
            Detail:    "Giữ người xem đến cuối bằng cách nhỏ giọt thông tin, kết bằng tiết lộ không ai ngờ"
        ),

        // ── Educational ──────────────────────────────────────────────────────
        new(
            Value:     "myth_busting",
            Label:     "💥 Lật tẩy điều mọi người tin sai",
            ShortDesc: "Niềm tin phổ biến → Bằng chứng phản bác → Sự thật thật sự",
            Detail:    "Chọn một điều ai cũng nghĩ là đúng rồi chứng minh ngược lại — cực dễ viral"
        ),
        new(
            Value:     "ranking",
            Label:     "🏆 Top [N] điều bạn chưa biết",
            ShortDesc: "Giới thiệu list → Từ thấp lên cao → Vị trí #1 gây tranh cãi",
            Detail:    "Format quen thuộc, người xem xem đến cuối để biết #1 — hạng bất ngờ tạo bình luận"
        ),
        new(
            Value:     "iceberg",
            Label:     "🧊 Sự thật ẩn sâu mà ít ai biết",
            ShortDesc: "Bề nổi ai cũng biết → Đào sâu dần → Tầng đáy tối tăm nhất",
            Detail:    "Bắt đầu từ điều hiển nhiên, mỗi lớp tiếp theo sốc hơn — giữ view rất tốt"
        ),

        // ── Viral / TikTok-specific ───────────────────────────────────────────
        new(
            Value:     "pov",
            Label:     "🎭 Đặt người xem vào góc nhìn nhân vật",
            ShortDesc: "Tình huống quen → Góc nhìn bất ngờ → Leo thang hài hước → Kết",
            Detail:    "\"POV: bạn là...\" — format cực viral trên TikTok, dễ gây đồng cảm và chia sẻ"
        ),
        new(
            Value:     "before_after",
            Label:     "🔄 Cuộc sống trước và sau khi biết điều này",
            ShortDesc: "Trước khi biết → Khoảnh khắc ngộ ra → Thay đổi hành vi → Lời khuyên",
            Detail:    "Người xem tự thấy mình trong đó — format dễ share vì ai cũng muốn tag bạn bè"
        ),
        new(
            Value:     "what_if",
            Label:     "❓ Điều gì xảy ra nếu... (giả thuyết domino)",
            ShortDesc: "Câu hỏi giả định → Kịch bản 1 → Kịch bản 2 → Hậu quả dây chuyền",
            Detail:    "Đặt giả thuyết kỳ lạ rồi dẫn dắt logic đến kết luận bất ngờ — kích thích tư duy"
        ),
    ];

    public static readonly List<ToneOption> Tones =
    [
        new(
            Value:     "storytelling",
            Label:     "Kể chuyện cảm xúc",
            Emoji:     "📖",
            ShortDesc: "Dẫn dắt từng bước, xây dựng đồng cảm"
        ),
        new(
            Value:     "genz_meme",
            Label:     "Gen Z / Meme",
            Emoji:     "😎",
            ShortDesc: "Hài hước, mỉa mai nhẹ, dùng ngôn ngữ trending"
        ),
        new(
            Value:     "serious",
            Label:     "Nghiêm túc / Báo chí",
            Emoji:     "🎓",
            ShortDesc: "Khách quan, chuyên sâu, không đùa cợt"
        ),
        new(
            Value:     "motivational",
            Label:     "Truyền cảm hứng",
            Emoji:     "🔥",
            ShortDesc: "Tích cực, năng lượng cao, kêu gọi hành động"
        ),
        new(
            Value:     "dark_humor",
            Label:     "Hài đen / Châm biếm",
            Emoji:     "🖤",
            ShortDesc: "Mỉa mai sắc bén, dám nói thẳng"
        ),
    ];

    public static readonly List<VoiceOption> Voices = 
    [
        new(
            Value:     "hn_female_ngochuyen_full_48k-fhg",
            Label:     "Nữ Miền Bắc",
            Emoji:     "👩🏻"
        ),
        new(
            Value:     "hn_male_manhdung_news_48k-fhg",
            Label:     "Nam Miền Bắc",
            Emoji:     "🧔🏻‍♂️"
        ),
        new(
            Value:     "hue_female_huonggiang_full_48k-fhg",
            Label:     "Nữ Miền Trung",
            Emoji:     "👩🏽‍🦱"
        ),
        new(
            Value:     "hue_male_duyphuong_full_48k-fhg",
            Label:     "Nam Miền Trung",
            Emoji:     "👨🏽‍🦱"
        ),
        new(
            Value:     "sg_female_lantrinh_vdts_48k-fhg",
            Label:     "Nữ Miền Nam",
            Emoji:     "👩🏻‍🦳"
        ),
        new(
            Value:     "sg_male_trungkien_vdts_48k-fhg",
            Label:     "Nam Miền Nam",
            Emoji:     "🧑🏻‍🦲"
        )
        ,
        new(
            Value:     "hn_male_phuthang_stor80dt_48k-fhg",
            Label:     "HN - Anh Khôi (Đọc chuyện)",
            Emoji:     "🧔🏻‍♂️"
        )
        ,
        new(
            Value:     "hn_male_phuthang_news65dt_44k-fhg",
            Label:     "HN - Anh Khôi (Tin tức)",
            Emoji:     "🧔🏻‍♂️"
        )
    ];

    public static readonly List<RatioOption> Ratios = 
    [
        new(
            Value:     "16:9",
            Label:     "Youtube (16:9)",
            Emoji:     "🖥️" 
        ),
        new(
            Value:     "9:16",
            Label:     "Facebook/TikTok (9:16)",
            Emoji:     "📱" 
        ),
        new(
            Value:     "1:1",
            Label:     "Instagram / Threads (1:1)",
            Emoji:     "🖼️" 
        )
    ];
}
