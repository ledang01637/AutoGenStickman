using System.Text.Json.Serialization;

namespace frontend.Models;

public class GoogleLoginReq
{
    [JsonPropertyName("token")]
    public string Token { get; set; } = string.Empty;
}
