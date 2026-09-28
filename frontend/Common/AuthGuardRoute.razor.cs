// AuthGuardRoute.razor.cs
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Routing;
using frontend.Common;
using frontend.Models;

namespace frontend.Common;

public partial class AuthGuardRoute : ComponentBase, IDisposable
{
    [Inject] private AppState AppState { get; set; } = default!;
    [Inject] private NavigationManager NavManager { get; set; } = default!;
    [Inject] private ApiService Api { get; set; } = default!;

    [Parameter] public RouteData RouteData { get; set; } = default!;

    private static readonly HashSet<string> _publicPages = new()
    {
        "/login", "/register", "/",
    };

    private bool _isReady = false;

    protected override async Task OnInitializedAsync()
    {
        NavManager.LocationChanged += OnLocationChanged;
        AppState.OnChange += OnStateChanged;

        if (!AppState.IsLoggedIn)
        {
            try
            {
                var result = await Api.GetAsync<ApiResult<UserProfileDTO>>("users/me");
                if (result is { IsSuccess: true, Data: not null })
                    AppState.CurrentUser = result.Data;
            }
            catch { }
        }

        CheckAuth();
    }

    protected override void OnParametersSet() => CheckAuth();

    private void OnLocationChanged(object? sender, LocationChangedEventArgs e)
    {
        CheckAuth();
        InvokeAsync(StateHasChanged);
    }

    private void OnStateChanged()
    {
        CheckAuth();
        InvokeAsync(StateHasChanged);
    }

    private void CheckAuth()
    {
        var currentPath = "/" + NavManager
            .ToBaseRelativePath(NavManager.Uri)
            .ToLower()
            .TrimStart('/')
            .Split('?')[0];

        bool isPublic   = _publicPages.Contains(currentPath);
        bool isLoggedIn = AppState.IsLoggedIn;

        if (isLoggedIn && currentPath == "/login")
        {
            NavManager.NavigateTo("/", forceLoad: false);
            return;
        }

        if (!isLoggedIn && !isPublic)
        {
            NavManager.NavigateTo("/login", forceLoad: false);
            return;
        }

        _isReady = true;
    }

    public void Dispose()
    {
        AppState.OnChange          -= OnStateChanged;
        NavManager.LocationChanged -= OnLocationChanged;
    }
}