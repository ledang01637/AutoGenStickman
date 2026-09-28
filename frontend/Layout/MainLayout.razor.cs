// File: Layout/MainLayout.razor.cs

using frontend.Common;
using frontend.Models;
using frontend.Services;
using frontend.Themes;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Routing;
using Microsoft.JSInterop;
using MudBlazor;
using MudBlazor.Services;

namespace frontend.Layout;

public partial class MainLayout : IAsyncDisposable, IBrowserViewportObserver
{
    [Inject] private AppState _appState { get; set; } = default!;
    [Inject] private ApiService _apiService { get; set; } = default!;
    [Inject] private NavigationManager NavigationManager { get; set; } = default!;
    [Inject] private IThemeStorageService _themeStorage { get; set; } = default!;
    [Inject] private IBrowserViewportService BrowserViewportService { get; set; } = default!;
    [Inject] private IJSRuntime JS { get; set; } = default!;

    private bool _drawerOpen = false;
    private bool _isDarkMode = true;
    private bool _isThemeLoaded = false;
    private bool _isDesktop = false;

    Guid IBrowserViewportObserver.Id { get; } = Guid.NewGuid();

    protected override async Task OnInitializedAsync()
    {
        _appState.OnChange += StateHasChanged;
        NavigationManager.LocationChanged += OnLocationChanged;

        try
        {
            _appState.IsLoadingUser = true;
            StateHasChanged();

            var response = await _apiService.GetAsync<ApiResult<UserProfileDTO>>("users/me");
            if (response?.Data != null)
                _appState.CurrentUser = response.Data;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainLayout] Lỗi load user: {ex.Message}");
        }
        finally
        {
            _appState.IsLoadingUser = false;
        }
    }

    private async void OnLocationChanged(object? sender, LocationChangedEventArgs e)
    {
        if (!_isDesktop && _drawerOpen)
        {
            _drawerOpen = false;
            await JS.InvokeVoidAsync("document.body.classList.remove", "drawer-open");
            await InvokeAsync(StateHasChanged);
        }
    }

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if (!firstRender) return;

        try
        {
            _isDarkMode = await _themeStorage.GetDarkModeAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainLayout] Lỗi đọc theme: {ex.Message}");
        }

        await BrowserViewportService.SubscribeAsync(this, fireImmediately: true);

        _isThemeLoaded = true;
        StateHasChanged();
    }

    async Task IBrowserViewportObserver.NotifyBrowserViewportChangeAsync(BrowserViewportEventArgs args)
    {
        var wasDesktop = _isDesktop;
        _isDesktop = IsDesktop(args.Breakpoint);

        if (!_isDesktop)
        {
            _drawerOpen = false;
            await JS.InvokeVoidAsync("document.body.classList.remove", "drawer-open");
        }
        else if (!wasDesktop && _isDesktop)
        {
            _drawerOpen = true;
        }

        await InvokeAsync(StateHasChanged);
    }

    private async Task HandleLogoutAsync()
    {
        try
        {
            await _apiService.PostAsync<object>("auth/logout", new { });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainLayout] Lỗi logout API: {ex.Message}");
        }
        finally
        {
            _appState.Logout();
            NavigationManager.NavigateTo("/login");
        }
    }

    private void NavigateToHome() => NavigationManager.NavigateTo("/");

    private async Task ToggleDrawer()
    {
        _drawerOpen = !_drawerOpen;

        if (!_isDesktop)
        {
            await JS.InvokeVoidAsync(
                _drawerOpen
                    ? "document.body.classList.add"
                    : "document.body.classList.remove",
                "drawer-open");
        }
    }

    private async Task ToggleThemeAsync()
    {
        _isDarkMode = !_isDarkMode;
        await _themeStorage.SetDarkModeAsync(_isDarkMode);
        StateHasChanged();
    }

    private static bool IsDesktop(Breakpoint bp)
        => bp >= Breakpoint.Md;

    public async ValueTask DisposeAsync()
    {
        _appState.OnChange -= StateHasChanged;
        NavigationManager.LocationChanged -= OnLocationChanged;
        await JS.InvokeVoidAsync("document.body.classList.remove", "drawer-open");
        await BrowserViewportService.UnsubscribeAsync(this);
    }

    private readonly MudTheme _saasTheme = SaasTheme.Instance;
}