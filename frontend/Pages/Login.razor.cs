using System.Text.Json;
using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;
using MudBlazor;
using frontend.Common;
using frontend.Models;
namespace frontend.Pages;

public partial class Login : ComponentBase, IAsyncDisposable
{
    [Inject] private IJSRuntime JS { get; set; } = default!;
    [Inject] private IConfiguration Config { get; set; } = default!;
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private NavigationManager NavManager { get; set; } = default!;
    [Inject] private AppState AppState { get; set; } = default!;

    private DotNetObjectReference<Login>? _objRef;
    private bool _isLoading;
    private string? _errorMessage;

    private readonly (string Icon, string Text)[] _features =
    {
        (Icons.Material.Filled.AutoAwesome,  "Tạo video AI tự động từ chủ đề bất kỳ"),
        (Icons.Material.Filled.Speed,        "Xuất video trong vài phút"),
        (Icons.Material.Filled.CloudDownload,"Tải về và chia sẻ dễ dàng"),
    };

    protected override Task OnInitializedAsync()
    {
        AppState.OnChange += OnAppStateChanged;

        if (AppState.IsLoggedIn)
            NavManager.NavigateTo("/", forceLoad: false);

        return Task.CompletedTask;
    }

    private void OnAppStateChanged()
    {
        if (AppState.IsLoggedIn)
            NavManager.NavigateTo("/", forceLoad: false);

        InvokeAsync(StateHasChanged);
    }

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if(firstRender)
            await JS.InvokeVoidAsync("loadGoogleScript");

        if (!firstRender) return;
        if (AppState.IsLoggedIn) return; 

        _objRef = DotNetObjectReference.Create(this);
        var clientId = Config["GoogleClientId"]
            ?? throw new InvalidOperationException("Thiếu cấu hình GoogleClientId.");

        await JS.InvokeVoidAsync("googleLoginHelper.initialize", clientId, _objRef);
    }

    // ==========================================
    // GOOGLE LOGIN CALLBACK
    // ==========================================
    [JSInvokable]
    public async Task OnGoogleLoginSuccess(string jwtToken)
    {
        if (string.IsNullOrWhiteSpace(jwtToken))
        {
            SetError("Token Google không hợp lệ.");
            return;
        }

        _isLoading = true;
        _errorMessage = null;
        StateHasChanged();

        try
        {
            var result = await Api.PostAsync<ApiResult<UserProfileDTO>>(
                "auth/login-google",
                new GoogleLoginReq { Token = jwtToken }
            );

            if (result is not { IsSuccess: true } || result.Data is null)
            {
                SetError(result?.Message ?? "Đăng nhập thất bại. Vui lòng thử lại.");
                return;
            }

            AppState.CurrentUser = result.Data;
            await InvokeAsync(() => 
            {
                NavManager.NavigateTo("/");
                StateHasChanged();
            });
        }
        catch (JsonException)
        {
            SetError("Lỗi phân tích dữ liệu từ server.");
        }
        catch (HttpRequestException)
        {
            SetError("Không thể kết nối đến server. Vui lòng thử lại.");
        }
        catch
        {
            SetError("Lỗi kết nối.");
        }
        finally
        {
            _isLoading = false;
            StateHasChanged();
        }
    }

    private void SetError(string message)
    {
        _errorMessage = message;
        _isLoading = false;
        StateHasChanged();
    }

    public async ValueTask DisposeAsync()
    {
        AppState.OnChange -= OnAppStateChanged;
        if (_objRef is not null)
        {
            try
            {
                await JS.InvokeVoidAsync("googleLoginHelper.dispose");
            }
            catch { }
            finally
            {
                _objRef.Dispose();
                _objRef = null;
            }
        }
    }
}