using System.Text.Json.Serialization;

namespace frontend.Models;

public class SubscriptionPlanResponse
{
    [JsonPropertyName("id")]
    public Guid Id { get; set; }

    [JsonPropertyName("plan_code")]
    public string PlanCode { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("monthly_price")]
    public decimal MonthlyPrice { get; set; }

    [JsonPropertyName("monthly_credits")]
    public int MonthlyCredits { get; set; }

    [JsonPropertyName("max_video_length_seconds")]
    public int MaxVideoLengthSeconds { get; set; }

    [JsonPropertyName("max_resolution")]
    public string MaxResolution { get; set; } = string.Empty;
}