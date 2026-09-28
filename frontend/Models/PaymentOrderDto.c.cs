// frontend/Models/PaymentDtos.cs
using System;
using System.Text.Json.Serialization;

namespace frontend.Models;

// Response từ POST /subscriptions/{plan_id}/subscribe
public sealed class SubscribeOrderDto
{
    [JsonPropertyName("order_id")]
    public Guid OrderId { get; set; }

    [JsonPropertyName("order_code")]
    public long OrderCode { get; set; }

    [JsonPropertyName("checkout_url")]
    public string CheckoutUrl { get; set; } = string.Empty;

    [JsonPropertyName("amount")]
    public int Amount { get; set; }

    [JsonPropertyName("plan_name")]
    public string PlanName { get; set; } = string.Empty;
}

// Response từ GET /payments/{order_id}
public sealed class PaymentOrderDto
{
    [JsonPropertyName("id")]
    public Guid Id { get; set; }

    [JsonPropertyName("order_code")]
    public long OrderCode { get; set; }

    [JsonPropertyName("amount")]
    public int Amount { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;  // PENDING/PAID/CANCELLED/FAILED

    [JsonPropertyName("checkout_url")]
    public string? CheckoutUrl { get; set; }

    [JsonPropertyName("plan_id")]
    public Guid? PlanId { get; set; }

    [JsonPropertyName("top_up_credits")]
    public int? TopUpCredits { get; set; }
}