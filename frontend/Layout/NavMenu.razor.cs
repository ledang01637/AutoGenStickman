// File: Layout/NavMenu.razor.cs

using frontend.Common;
using Microsoft.AspNetCore.Components;
using MudBlazor;

namespace frontend.Layout;

public partial class NavMenu
{
    [Inject] private AppState _appState { get; set; } = default!;

    [CascadingParameter(Name = "DrawerOpen")]
    private bool DrawerOpen { get; set; }

    [CascadingParameter(Name = "IsDesktop")]
    private bool IsDesktop { get; set; }

    // Tooltip chỉ hiện khi desktop Mini drawer đang collapsed
    private bool _showTooltips => IsDesktop && !DrawerOpen;

    // Free hoặc Basic → hiện Nâng cấp, còn lại → Nạp thêm
    private bool _isFreePlan
    {
        get
        {
            var plan = _appState.CurrentUser?.Plan?.ToLowerInvariant() ?? "free";
            return plan == "free" || plan == "basic";
        }
    }

    // Màu chip theo plan
    private Color _planChipColor
    {
        get
        {
            var plan = _appState.CurrentUser?.Plan?.ToLowerInvariant() ?? "free";
            return plan switch
            {
                "premium" => Color.Success,
                "pro"     => Color.Primary,
                _         => Color.Default
            };
        }
    }
}