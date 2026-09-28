// frontend/Pages/Topup.razor.cs
using Microsoft.AspNetCore.Components;
using MudBlazor;
using frontend.Common;
using Microsoft.JSInterop;

namespace frontend.Pages;

public record TopupPreset(
    int Credits,
    bool IsPopular = false,
    string BadgeText = ""
);

public partial class Topup : ComponentBase, IDisposable
{
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;
    [Inject] private AppState AppState { get; set; } = default!;
    [Inject] private NavigationManager Nav { get; set; } = default!;
    [Inject] private IJSRuntime JS { get; set; } = default!;
    [Inject] private IConfiguration Configuration { get; set; } = default!;

    private int _creditPriceVnd;
    public const int MIN_CREDITS      = 20;
    public const int MAX_CREDITS      = 4_000;

    private int  _customCredits = 40;
    private bool _isProcessing  = false;

    protected override void OnInitialized()
    {
        _creditPriceVnd = Configuration.GetValue<int>("CREDIT_PRICE_VND", 1000);

        AppState.OnChange += StateHasChanged;

        var popular = Presets.FirstOrDefault(p => p.IsPopular);
        if (popular is not null)
            _customCredits = popular.Credits;
    }

    public static readonly List<TopupPreset> Presets =
    [
        new(Credits: 20,  BadgeText: ""),
        new(Credits: 40,  IsPopular: true, BadgeText: "Phổ biến"),
        new(Credits: 80,  BadgeText: ""),
        new(Credits: 160, BadgeText: ""),
        new(Credits: 320, BadgeText: ""),
        new(Credits: 640, BadgeText: ""),
    ];


    private void OnCustomCreditsChanged(int value) => _customCredits = value;
    private void SelectPreset(int credits)         => _customCredits = credits;
    private int GetPresetPrice(TopupPreset preset) => preset.Credits * _creditPriceVnd;
    private bool IsPresetSelected(int credits) => _customCredits == credits;
    private int  GetFinalCredits()             => _customCredits;
    private int  GetFinalPrice()               => _customCredits * _creditPriceVnd;
    private bool IsValidAmount()               =>
        _customCredits >= MIN_CREDITS && _customCredits <= MAX_CREDITS;

    private string FormatPrice(int price) => FormatPriceStatic(price);

    private string GetPresetCardClass(TopupPreset preset)
    {
        var classes = new List<string> { "topup-preset-card", "text-center" };
        if (IsPresetSelected(preset.Credits)) classes.Add("topup-preset-selected");
        if (preset.IsPopular)                 classes.Add("topup-preset-popular");
        return string.Join(" ", classes);
    }

    internal static string FormatPriceStatic(int price)
        => price.ToString("N0", System.Globalization.CultureInfo.GetCultureInfo("vi-VN"));

    private async Task TopupAsync()
    {
        if (_isProcessing) return;

        var credits = GetFinalCredits();
        if (credits < MIN_CREDITS)
        {
            Snackbar.Add($"Số credit tối thiểu là {MIN_CREDITS}.", Severity.Warning);
            return;
        }
        if (credits > MAX_CREDITS)
        {
            Snackbar.Add($"Tối đa {MAX_CREDITS:N0} credit/lần.", Severity.Warning);
            return;
        }

        _isProcessing = true;
        StateHasChanged();

        try
        {
            var result = await Api.PostAsync<ApiResult<TopupOrderDto>>(
                "payments/top-up",
                new { credits }
            );

            if (result?.IsSuccess != true || result.Data is null)
            {
                Snackbar.Add(result?.Message ?? "Tạo đơn nạp thất bại.", Severity.Error);
                return;
            }

            var checkoutUrl = result.Data.CheckoutUrl;
            if (string.IsNullOrWhiteSpace(checkoutUrl))
            {
                Snackbar.Add("Không nhận được link thanh toán.", Severity.Error);
                return;
            }

            Snackbar.Add(
                $"Đang chuyển sang PayOS để nạp {credits:N0} credit ({GetFinalPrice():N0}đ)...",
                Severity.Info
            );

            await JS.InvokeVoidAsync("localStorage.setItem", "payment_return_url", "/topup");
            Nav.NavigateTo(checkoutUrl, forceLoad: true);
        }
        catch
        {
            Snackbar.Add($"Lỗi kết nối", Severity.Error);
        }
        finally
        {
            _isProcessing = false;
            StateHasChanged();
        }
    }

    public void Dispose()
    {
        AppState.OnChange -= StateHasChanged;
        GC.SuppressFinalize(this);
    }
}

public sealed class TopupOrderDto
{
    [System.Text.Json.Serialization.JsonPropertyName("order_id")]
    public Guid OrderId { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("order_code")]
    public long OrderCode { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("checkout_url")]
    public string CheckoutUrl { get; set; } = string.Empty;

    [System.Text.Json.Serialization.JsonPropertyName("amount")]
    public int Amount { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("credits")]
    public int Credits { get; set; }
}