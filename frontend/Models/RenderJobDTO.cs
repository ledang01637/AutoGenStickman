// Models/VideoModels.cs
using System.Text.Json.Serialization;

namespace frontend.Models;

public class RenderJobDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("output_url")]
    public string? OutputUrl { get; set; }

    [JsonPropertyName("cost_credits")]
    public int CostCredits { get; set; }

    [JsonPropertyName("duration_seconds")]
    public int DurationSeconds { get; set; }

    [JsonPropertyName("created_at")]
    public DateTimeOffset CreatedAt { get; set; }

    [JsonPropertyName("completed_at")]
    public DateTimeOffset? CompletedAt { get; set; }

    [JsonPropertyName("error_message")]
    public string? ErrorMessage { get; set; }

    [JsonPropertyName("retry_count")]
    public int RetryCount { get; set; }    

    [JsonPropertyName("max_retries")]
    public int MaxRetries { get; set; } = 3; 

    public DateTimeOffset CreatedAtLocal => CreatedAt.ToLocalTime();
}

public class VideoProjectDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("created_at")]
    public DateTimeOffset CreatedAt { get; set; }

    [JsonPropertyName("latest_job")]
    public RenderJobDto? LatestJob { get; set; }

    // ✅ Local time để hiển thị trong UI
    public DateTimeOffset CreatedAtLocal => CreatedAt.ToLocalTime();

    // ==========================================
    // COMPUTED — UI LOGIC
    // ==========================================

    public VideoDisplayStatus DisplayStatus => LatestJob?.Status switch
    {
        "COMPLETED"            => IsExpired      ? VideoDisplayStatus.Expired
                                : IsExpiringSoon ? VideoDisplayStatus.ExpiringSoon
                                                : VideoDisplayStatus.Ready,
        "PROCESSING"           => VideoDisplayStatus.Processing,
        "PENDING"              => VideoDisplayStatus.Pending,
        "FAILED"               => LatestJob.RetryCount >= LatestJob.MaxRetries
                                    ? VideoDisplayStatus.Failed      
                                    : VideoDisplayStatus.Processing,
        "INSUFFICIENT_CREDITS" => VideoDisplayStatus.InsufficientCredits,
        "RENDER_QUEUED"        => VideoDisplayStatus.RenderQueued,
        
        _                      => VideoDisplayStatus.Unknown,
    };

    // ✅ Dùng DateTimeOffset.UtcNow — nhất quán với DateTimeOffset
    public bool IsExpired =>
        LatestJob?.CompletedAt is not null &&
        (DateTimeOffset.UtcNow - LatestJob.CompletedAt.Value).TotalHours >= 1;

    public bool IsExpiringSoon =>
        LatestJob?.CompletedAt is not null &&
        !IsExpired &&
        (DateTimeOffset.UtcNow - LatestJob.CompletedAt.Value).TotalMinutes >= 45;

    public string DurationDisplay =>
        LatestJob is null ? "--" :
        LatestJob.DurationSeconds >= 60
            ? $"{LatestJob.DurationSeconds / 60}p {LatestJob.DurationSeconds % 60}s"
            : $"{LatestJob.DurationSeconds}s";

    public string TimeRemainingDisplay
    {
        get
        {
            if (LatestJob?.CompletedAt is null) return string.Empty;
            var remaining = TimeSpan.FromHours(1) -
                            (DateTimeOffset.UtcNow - LatestJob.CompletedAt.Value);
            if (remaining <= TimeSpan.Zero) return "Đã hết hạn";
            return remaining.TotalMinutes < 1
                ? "Còn dưới 1 phút"
                : $"Còn {(int)remaining.TotalMinutes} phút";
        }
    }
}

public enum VideoDisplayStatus
{

    Pending,              // Đang chờ trong hàng đợi
    Processing,           // Đang tạo video
    Ready,                // Hoàn thành, còn tải được
    ExpiringSoon,         // Sắp hết hạn (< 15 phút)
    Expired,              // Đã hết hạn, URL không còn
    Failed,               // Lỗi khi tạo
    InsufficientCredits,  // Thiếu credit
    RenderQueued,         // Đang trong hàng chờ
    Unknown,
}