using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;
using MudBlazor;
using frontend.Common;

namespace frontend.Layout;

public partial class SimpleLayout : LayoutComponentBase
{
    [Inject] private IJSRuntime JS { get; set; } = default!;
    [Inject] private NavigationManager NavigationManager { get; set; } = default!;
    [Inject] private AppState _appState { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;

    private bool _isDarkMode = true;

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if (firstRender)
        {
            var savedTheme = await JS.InvokeAsync<string>("localStorage.getItem", "saas_dark_mode");
            if (!string.IsNullOrEmpty(savedTheme))
            {
                _isDarkMode = bool.Parse(savedTheme);
                StateHasChanged();
            }
        }
    }

    private async Task ToggleThemeAsync()
    {
        _isDarkMode = !_isDarkMode;
        await JS.InvokeVoidAsync("localStorage.setItem", "saas_dark_mode", _isDarkMode.ToString().ToLower());
    }

    private async Task HandleLogoutAsync()
    {
        // copy logic logout từ MainLayout của bạn vào đây
        await JS.InvokeVoidAsync("localStorage.removeItem", "auth_token");
        _appState.Logout();
        NavigationManager.NavigateTo("/login", forceLoad: true);
    }

    private readonly MudTheme _saasTheme = new MudTheme()
    {
        PaletteLight = new PaletteLight()
        {
            Primary = "#4169E1",
            Secondary = "#50C878",
            Background = "#f8fafc",
            Surface = "#ffffff",
            AppbarBackground = "rgba(255, 255, 255, 0.85)",
            AppbarText = "#1e293b",
            DrawerBackground = "#ffffff"
        },
        PaletteDark = new PaletteDark()
        {
            Primary = "#4169E1",
            Secondary = "#50C878",
            Background = "#0f111a",
            Surface = "#1a1d27",
            TextPrimary = "#e2e8f0",
            TextSecondary = "#94a3b8",
            AppbarBackground = "rgba(21, 24, 33, 0.85)",
            AppbarText = "#e2e8f0",
            DrawerBackground = "#151821",
        },
        Typography = new Typography()
        {
            Default =
            {
                FontFamily = new[] { "Inter", "Helvetica", "Arial", "sans-serif" },
                FontSize = "0.875rem",
                FontWeight = "400"
            },
            H5 =
            {
                FontFamily = new[] { "Inter", "Helvetica", "Arial", "sans-serif" },
                FontWeight = "700"
            },
            Subtitle1 =
            {
                FontFamily = new[] { "Inter", "Helvetica", "Arial", "sans-serif" },
                FontWeight = "600"
            }
        }
    };
}