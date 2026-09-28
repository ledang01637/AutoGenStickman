// frontend/Common/PlanFeatures.cs
namespace frontend.Common;

public static class PlanFeatures
{
    // ═══════════════════════════════════════════
    // THỜI LƯỢNG
    // ═══════════════════════════════════════════
    public static float GetMaxMinutes(string plan) => plan?.ToUpper() switch
    {
        "ULTRA" => 5f,
        "PRO"   => 3f,
        "TRIAL" => 3f,
        "BASIC" => 1f,  
        _       => 0.5f,
    };

    // ═══════════════════════════════════════════
    // PACE
    // Free:  balanced + dynamic (tạo Aha Moment)
    // Basic: + storytelling
    // Pro:   + fast_cut
    // Ultra: + cinematic
    // ═══════════════════════════════════════════

    public static bool CanChooseRenderTier(string plan) =>
        plan?.ToUpper() is "FREE";

    /// Được phép chọn pace hay không (Basic trở lên mới vào panel)
    public static bool CanCustomizePace(string plan) =>
        plan?.ToUpper() is "BASIC" or "PRO" or "ULTRA" or "TRIAL" or "FREE";

    /// Được phép chọn giọng đọc
    public static bool CanCustomizeVoice(string plan) =>
        plan?.ToUpper() is "BASIC" or "PRO" or "ULTRA" or "TRIAL" or "FREE";

    /// Fast Cut — Pro trở lên (key selling point của Pro)
    public static bool CanUseFastCut(string plan) =>
        plan?.ToUpper() is "PRO" or "ULTRA" or "TRIAL";

    /// Cinematic — Ultra only (render nặng, context lớn)
    public static bool CanUseCinematic(string plan) =>
        plan?.ToUpper() is "ULTRA";

    /// Danh sách pace được phép dùng theo plan
    public static IReadOnlyList<string> GetAllowedPaces(string? plan) =>
        plan?.ToUpper() switch
        {
            "ULTRA"         => ["balanced", "dynamic", "storytelling", "fast_cut", "cinematic"],
            "PRO" or "TRIAL"=> ["balanced", "dynamic", "storytelling", "fast_cut"],
            "BASIC"         => ["balanced", "dynamic", "storytelling"],
            _               => ["balanced", "dynamic"],
        };

    public static IReadOnlyList<string> GetAllowedVoices(string? plan) =>
    plan?.ToUpper() switch
    {
        "ULTRA"          => [
            "hn_female_ngochuyen_full_48k-fhg",     // 👩🏻 Nữ Miền Bắc      (Free)
            "hn_male_manhdung_news_48k-fhg",        // 🧔🏻‍♂️ Nam Miền Bắc    (Basic)
            "sg_female_lantrinh_vdts_48k-fhg",      // 👩🏻‍🦳 Nữ Miền Nam     (Basic)
            "sg_male_trungkien_vdts_48k-fhg",       // 🧑🏻‍🦲 Nam Miền Nam    (Pro)
            "hue_female_huonggiang_full_48k-fhg",   // 👩🏽‍🦱 Nữ Miền Trung   (Pro)
            "hue_male_duyphuong_full_48k-fhg",      // 👨🏽‍🦱 Nam Miền Trung  (Pro)
            "hn_male_phuthang_stor80dt_48k-fhg",    // 🧔🏻‍♂️ HN - Anh Khôi (Đọc chuyện) (Pro)
            "hn_male_phuthang_news65dt_44k-fhg",    // 🧔🏻‍♂️ HN - Anh Khôi (Tin tức) (Pro)
        ],
        "PRO" or "TRIAL" => [
            "hn_female_ngochuyen_full_48k-fhg",     // 👩🏻 Nữ Miền Bắc      (Free)
            "hn_male_manhdung_news_48k-fhg",        // 🧔🏻‍♂️ Nam Miền Bắc    (Basic)
            "sg_female_lantrinh_vdts_48k-fhg",      // 👩🏻‍🦳 Nữ Miền Nam     (Basic)
            "sg_male_trungkien_vdts_48k-fhg",       // 🧑🏻‍🦲 Nam Miền Nam    (Pro)
            "hue_female_huonggiang_full_48k-fhg",   // 👩🏽‍🦱 Nữ Miền Trung   (Pro)
            "hue_male_duyphuong_full_48k-fhg",      // 👨🏽‍🦱 Nam Miền Trung  (Pro)
            "hn_male_phuthang_stor80dt_48k-fhg",    // 🧔🏻‍♂️ HN - Anh Khôi (Đọc chuyện) (Pro)
            "hn_male_phuthang_news65dt_44k-fhg",    // 🧔🏻‍♂️ HN - Anh Khôi (Tin tức) (Pro)
        ],
        "BASIC"          => [
            "hn_female_ngochuyen_full_48k-fhg",     // 👩🏻 Nữ Miền Bắc      (Free)
            "hn_male_manhdung_news_48k-fhg",        // 🧔🏻‍♂️ Nam Miền Bắc    (Basic)
            "sg_female_lantrinh_vdts_48k-fhg",      // 👩🏻‍🦳 Nữ Miền Nam     (Basic)
        ],
        _                => [
            "hn_female_ngochuyen_full_48k-fhg",     // 👩🏻 Nữ Miền Bắc      (Free)
        ],
    };   

    // ═══════════════════════════════════════════
    // STORY STRUCTURE
    // Free:  problem_solve, ranking
    // Basic: + timeline, hero_journey, myth_busting, before_after
    // Pro:   + hook_twist, debate, rags_to_riches, pov, what_if
    // Ultra: + fall_from_grace, mystery_reveal, iceberg
    // ═══════════════════════════════════════════
    public static bool CanCustomizeStoryStructure(string plan) =>
        plan?.ToUpper() is "BASIC" or "PRO" or "ULTRA" or "TRIAL" or "FREE";

    public static IReadOnlyList<string> GetAllowedStructures(string? plan) =>
        plan?.ToUpper() switch
        {
            "ULTRA" =>
            [
                "problem_solve", "ranking",
                "timeline", "hero_journey", "myth_busting", "before_after",
                "hook_twist", "debate", "rags_to_riches", "pov", "what_if",
                "fall_from_grace", "mystery_reveal", "iceberg",
            ],
            "PRO" or "TRIAL" =>
            [
                "problem_solve", "ranking",
                "timeline", "hero_journey", "myth_busting", "before_after",
                "hook_twist", "debate", "rags_to_riches", "pov", "what_if",
            ],
            "BASIC" =>
            [
                "problem_solve", "ranking",
                "timeline", "hero_journey", "myth_busting", "before_after",
            ],
            _ => ["problem_solve", "ranking"], // FREE
        };

    // ═══════════════════════════════════════════
    // TONE
    // Free:  serious
    // Basic: + storytelling, motivational
    // Pro:   + genz_meme
    // Ultra: + dark_humor
    // ═══════════════════════════════════════════
    public static IReadOnlyList<string> GetAllowedTones(string? plan) =>
        plan?.ToUpper() switch
        {
            "ULTRA"          => ["serious", "storytelling", "motivational", "genz_meme", "dark_humor"],
            "PRO" or "TRIAL" => ["serious", "storytelling", "motivational", "genz_meme"],
            "BASIC"          => ["serious", "storytelling", "motivational"],
            _                => ["serious"],
        };

    public static bool IsToneLocked(string toneValue, string? plan) =>
        !GetAllowedTones(plan).Contains(toneValue);

    // ═══════════════════════════════════════════
    // NHÂN VẬT CHÍNH
    // Pro trở lên mới được tuỳ chỉnh
    // ═══════════════════════════════════════════
    public static bool CanCustomizeCharacter(string plan) =>
        plan?.ToUpper() is "PRO" or "ULTRA" or "TRIAL";

    // ═══════════════════════════════════════════
    // AI MODEL
    // Pro trở lên (fix: trước chỉ Ultra+Trial)
    // ═══════════════════════════════════════════
    public static bool CanUseBestModel(string plan) =>
        plan?.ToUpper() is "PRO" or "ULTRA" or "TRIAL";     


    // Pro trở lên (fix: trước chỉ Ultra+Trial)
    // ═══════════════════════════════════════════
    public static bool CanUseColorImage(string plan) =>
        plan?.ToUpper() is "PRO" or "ULTRA" or "TRIAL";         

    // ═══════════════════════════════════════════
    // DISPLAY HELPERS
    // ═══════════════════════════════════════════
    public static string GetDisplayName(string plan) => plan?.ToUpper() switch
    {
        "ULTRA" => "Ultra",
        "PRO"   => "Pro",
        "TRIAL" => "Dùng thử",
        "BASIC" => "Basic",
        _       => "Free",
    };

    public static string GetPlanColor(string plan) => plan?.ToUpper() switch
    {
        "ULTRA" => "#F59E0B",
        "PRO"   => "#8B5CF6",
        "TRIAL" => "#10B981",
        "BASIC" => "#7b9fe7",
        _       => "#abafb7",
    };

    /// Tên gói tối thiểu cần để mở một pace cụ thể (dùng cho upgrade dialog)
    public static string GetRequiredPlanForPace(string paceValue) => paceValue switch
    {
        "cinematic" => "ULTRA",
        "fast_cut"  => "PRO",
        "storytelling" => "BASIC",
        _ => "FREE",
    };

    /// Tên gói tối thiểu cần để mở một structure cụ thể
    public static string GetRequiredPlanForStructure(string structureValue) => structureValue switch
    {
        "fall_from_grace" or "mystery_reveal" or "iceberg"             => "ULTRA",
        "hook_twist" or "debate" or "rags_to_riches" or "pov" or "what_if" => "PRO",
        "timeline" or "hero_journey" or "myth_busting" or "before_after"   => "BASIC",
        _ => "FREE",
    };

    public static string GetRequiredPlanForVoice(string voiceValue) => voiceValue switch
    {
        "hn_male_manhdung_news_48k-fhg"    => "BASIC",    // 🧔🏻‍♂️ Nam Miền Bắc
        "sg_female_lantrinh_vdts_48k-fhg"  => "BASIC",    // 👩🏻‍🦳 Nữ Miền Nam
        
        "sg_male_trungkien_vdts_48k-fhg"   => "PRO",        // 🧑🏻‍🦲 Nam Miền Nam
        "hue_female_huonggiang_full_48k-fhg" => "PRO",      // 👩🏽‍🦱 Nữ Miền Trung
        "hue_male_duyphuong_full_48k-fhg"  => "PRO",        // 👨🏽‍🦱 Nam Miền Trung
        "hn_male_phuthang_stor80dt_48k-fhg" => "PRO",        // 🧔🏻‍♂️ HN - Anh Khôi (Đọc chuyện)
        "hn_male_phuthang_news65dt_44k-fhg" => "PRO",        // 🧔🏻‍♂️ HN - Anh Khôi (Tin tức)
        _ => "FREE",  
    };

    /// Tên gói tối thiểu cần để mở một tone cụ thể
    public static string GetRequiredPlanForTone(string toneValue) => toneValue switch
    {
        "dark_humor"  => "ULTRA",
        "genz_meme"   => "PRO",
        "storytelling" or "motivational" => "BASIC",
        _ => "FREE",
    };
}
