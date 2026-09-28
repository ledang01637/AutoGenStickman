// frontend/Pages/Pricing.razor.cs
using Microsoft.AspNetCore.Components;
using MudBlazor;
using frontend.Common;
using frontend.Models;
using Microsoft.JSInterop;

namespace frontend.Pages;

public record PlanFeature(string Text, bool IsIncluded = true);

public record PlanInfo(
    Guid Id,
    string PlanCode,
    string Name,
    string Description,
    int MonthlyPrice,
    int MonthlyCredits,
    List<PlanFeature> Features,
    bool IsPro = false,
    bool IsFree = false
);

public partial class Pricing : ComponentBase, IDisposable
{
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;
    [Inject] private AppState AppState { get; set; } = default!;
    [Inject] private NavigationManager Nav { get; set; } = default!;
    [Inject] private IJSRuntime JS { get; set; } = default!;

    private bool _isYearly = false;
    private bool _isSubscribing = false;

    private string _currentPlan => AppState.CurrentUser?.Plan ?? "FREE";

    private static readonly List<PlanInfo> Plans =
    [
        new(
            Id:             Guid.Parse("b244bd80-8b33-4580-b041-7cea981f42b4"),
            PlanCode:       "BASIC",
            Name:           "Basic",
            Description:    "Khởi động kênh — Tập trung làm video review & chốt sale.",
            MonthlyPrice:   99_000,
            MonthlyCredits: 110,
            IsFree:         false,
            Features:
            [
                new("110 Credits / tháng (Khoảng 15 video)"),
                new("Video thời lượng ngắn (tối đa 1 phút)"),
                new("Nhịp độ chuyển cảnh tiêu chuẩn"),
                new("Giọng đọc cơ bản (Nghiêm túc, Truyền cảm hứng)"),
                new("Kịch bản chốt sale (Before/After, Review sản phẩm)"),
                new("Ưu tiên hàng đợi",  IsIncluded: false),
                new("Mô hình AI tốt nhất",            IsIncluded: false),
                new("Tuỳ chỉnh nhân vật chính",                IsIncluded: false),
                new("Tùy chỉnh giọng đọc",      IsIncluded: false),
            ]
        ),
        new(
            Id:             Guid.Parse("8b003dbe-2a6a-428c-908e-ed1eb0007b28"),
            PlanCode:       "PRO",
            Name:           "Pro",
            Description:    "Vũ khí cày view — Tối ưu giữ chân người xem để cắn đề xuất.",
            MonthlyPrice:   199_000,
            MonthlyCredits: 370,
            IsPro:          true,
            Features:
            [
                new("370 Credits / tháng (Khoảng 50 video)"),
                new("Video thời lượng trung bình (tối đa 2 phút)"),
                new("Chuyển cảnh dồn dập (Chống vuốt lướt trên TikTok/Shorts)"),
                new("Full giọng nói 3 miền"),
                new("Tuỳ chỉnh nhân vật chính theo ý muốn"),
                new("Mô hình AI tạo ảnh tốt nhất"),
                new("Ảnh có thêm màu sắc"),
                new("Nhịp độ điện ảnh (Cho video YouTube dài)", IsIncluded: false),
                new("Kịch bản hồ sơ bí ẩn / Thuyết âm mưu",    IsIncluded: false),
            ]
        ),
        new(
            Id:             Guid.Parse("e10973bd-8d61-4dce-bdd2-041ce22e2713"),
            PlanCode:       "ULTRA",
            Name:           "Ultra",
            Description:    "Xây kênh YouTube tự động — Chuyên làm video kể chuyện dài.",
            MonthlyPrice:   499_000,
            MonthlyCredits: 920,
            Features:
            [
                new("920 Credits / tháng (Khoảng 130 video)"),
                new("Video thời lượng dài (tối đa 3 phút)"),
                new("Mở khóa toàn bộ kho tính năng của gói Pro"),
                new("Ưu tiên hàng đợi cao nhất"),
                new("Hỗ trợ trợ theo ý muốn"),
                new("Hỗ trợ thêm giọng nói"),
                new("Hỗ trợ 1 - 1"),
                new("Muốn gì cũng được"),
                new("Trừ những thứ không làm được"),
            ]
        ),
    ];

    private static readonly PlanInfo PlanTrial = new(
        Id:             Guid.Parse("f9bc50c8-cfbe-4229-846f-f8911a74e8c5"),
        PlanCode:       "TRIAL",
        Name:           "Dùng thử Pro 7 Ngày",
        Description:    "Kiểm chứng sức mạnh của AI. Trải nghiệm ngay kịch bản Viral và Giọng đọc Gen Z.",
        MonthlyPrice:   29_000,
        MonthlyCredits: 55,    
        IsPro:          true,
        Features:       
        [
            new("Mở khóa 100% tính năng Gói Pro trong 7 ngày"),
            new("55 Credits (Ít nhất 7 video)")
        ]
    );

    private static List<PlanFeature> ProPlanFeatures
        => Plans.First(p => p.PlanCode == "PRO").Features;

    protected override void OnInitialized()
    {
        AppState.OnChange += StateHasChanged;
    }

    private async Task SubscribeAsync(Guid planId, string planCode, string planName)
    {
        if (_isSubscribing) return;
        _isSubscribing = true;
        StateHasChanged();

        try
        {
            // Backend trả về checkout_url của PayOS — KHÔNG kích hoạt sub ngay.
            // Sub chỉ active khi webhook PAID về.
            var result = await Api.PostAsync<ApiResult<SubscribeOrderDto>>(
                $"subscriptions/{planId}/subscribe",
                new { }
            );

            if (result?.IsSuccess != true || result.Data is null)
            {
                Snackbar.Add(result?.Message ?? "Tạo đơn thanh toán thất bại.", Severity.Error);
                return;
            }

            var checkoutUrl = result.Data.CheckoutUrl;
            if (string.IsNullOrWhiteSpace(checkoutUrl))
            {
                Snackbar.Add("Không nhận được link thanh toán từ máy chủ.", Severity.Error);
                return;
            }

            // Hiển thị thông báo trước khi redirect (UX rõ ràng cho user biết đang chuyển sang PayOS)
            Snackbar.Add($"Đang chuyển sang trang thanh toán PayOS cho gói {planName}...", Severity.Info);

            await JS.InvokeVoidAsync("localStorage.setItem", "payment_return_url", "/pricing");
            Nav.NavigateTo(checkoutUrl, forceLoad: true);

        }
        catch
        {
            Snackbar.Add("Lỗi kết nối", Severity.Error);
        }
        finally
        {
            _isSubscribing = false;
            StateHasChanged();
        }
    }

    private int GetDisplayPrice(PlanInfo plan)
        => _isYearly ? (int)(plan.MonthlyPrice * 0.8) : plan.MonthlyPrice;

    private bool IsCurrentPlan(string planCode)
        => string.Equals(_currentPlan, planCode, StringComparison.OrdinalIgnoreCase);

    private string GetCardClass(PlanInfo plan)
    {
        var baseClass = "pricing-card pa-6 d-flex flex-column h-100";
        if (plan.IsPro) baseClass += " card-pro position-relative";
        return baseClass;
    }

    private Color GetTitleColor(PlanInfo plan)
    {
        if (plan.IsPro) return Color.Primary;
        if (plan.PlanCode == "ULTRA") return Color.Warning;
        return Color.Default;
    }

    private Variant GetButtonVariant(PlanInfo plan)
        => plan.IsPro ? Variant.Filled : Variant.Outlined;

    private Color GetButtonColor(PlanInfo plan)
    {
        if (plan.IsPro) return Color.Primary;
        if (plan.PlanCode == "ULTRA") return Color.Warning;
        return Color.Default;
    }

    private string GetButtonClass(PlanInfo plan)
    {
        var baseClass = "mt-auto rounded-lg py-2";
        if (plan.IsPro) baseClass += " fw-bold shadow-md";
        else if (plan.PlanCode == "ULTRA") baseClass += " fw-bold";
        return baseClass;
    }

    private string GetButtonText(PlanInfo plan)
    {
        if (IsCurrentPlan(plan.PlanCode)) return "Gói hiện tại";
        if (plan.IsPro) return $"Nâng cấp {plan.Name}";
        return $"Đăng ký {plan.Name}";
    }

    private string FormatPrice(int price)
        => price.ToString("N0", System.Globalization.CultureInfo.GetCultureInfo("vi-VN"));

    public void Dispose()
    {
        AppState.OnChange -= StateHasChanged;
    }
}