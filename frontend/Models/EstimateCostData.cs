// frontend/Models/EstimateCostData.cs
using System.Text.Json.Serialization;

namespace frontend.Models;

public sealed class EstimateCostData
{
    [JsonPropertyName("cost_credits")]
    public int CostCredits { get; set; }

    [JsonPropertyName("total_scenes")]
    public int TotalScenes { get; set; }

    [JsonPropertyName("minutes")]
    public float Minutes { get; set; }

    [JsonPropertyName("effective_pace")]
    public string EffectivePace { get; set; } = string.Empty;

    [JsonPropertyName("pace_locked")]
    public bool PaceLocked { get; set; }

    [JsonPropertyName("current_balance")]
    public int CurrentBalance { get; set; }

    [JsonPropertyName("can_afford")]
    public bool CanAfford { get; set; }

    [JsonPropertyName("missing_credits")]
    public int MissingCredits { get; set; }
}