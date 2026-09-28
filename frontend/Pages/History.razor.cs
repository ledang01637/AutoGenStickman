using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;
using MudBlazor;
using frontend.Common;
using frontend.Models;

namespace frontend.Pages;

public partial class History : ComponentBase, IAsyncDisposable
{
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private AppState AppState { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;
    [Inject] private NavigationManager NavManager { get; set; } = default!;
    [Inject] private IJSRuntime JS { get; set; } = default!;

    private bool _isLoading = true;
    private List<VideoProjectDto> _videos = new();
    private string _videosHash = "";

    private System.Threading.Timer? _refreshTimer;
    private bool _hasActiveJobs => _videos.Any(v =>
        v.DisplayStatus is VideoDisplayStatus.Pending or VideoDisplayStatus.Processing
    );

    protected override async Task OnInitializedAsync()
    {
        AppState.OnChange += StateHasChanged;

        if (!AppState.IsLoggedIn)
        {
            NavManager.NavigateTo("/login", forceLoad: false);
            return;
        }

        await LoadVideosAsync();
        StartAutoRefreshIfNeeded();
    }

    private async Task LoadVideosAsync()
    {
        if (!_videos.Any())
        {
            _isLoading = true;
            StateHasChanged();
        }

        try
        {
            var result = await Api.GetAsync<ApiResult<List<VideoProjectDto>>>("videos/my-videos");

            if (result is { IsSuccess: true, Data: not null })
            {
                // Chỉ re-render nếu data thay đổi
                var newHash = ComputeHash(result.Data);
                if (newHash != _videosHash)
                {
                    _videos = result.Data;
                    _videosHash = newHash;
                    await SyncUserIfNeededAsync();
                    StateHasChanged();
                }
            }
            else
                Snackbar.Add(result?.Message ?? "Không thể tải danh sách video.", Severity.Warning);
        }
        catch
        {
            Snackbar.Add("Lỗi kết nối. Vui lòng thử lại.", Severity.Error);
        }
        finally
        {
            if (_isLoading)
            {
                _isLoading = false;
                StateHasChanged();
            }
        }
    }

    private static string ComputeHash(List<VideoProjectDto> videos)
    {
        // Hash dựa trên status + output_url của mỗi video
        var sb = new System.Text.StringBuilder();
        foreach (var v in videos)
        {
            sb.Append(v.Id);
            sb.Append(v.DisplayStatus);
            sb.Append(v.LatestJob?.OutputUrl);
        }
        return sb.ToString();
    }

    private async Task SyncUserIfNeededAsync()
    {
        // Sync lại user nếu có bất kỳ job failed nào
        // (credit có thể đã được hoàn lại từ backend)
        var hasFailedJobs = _videos.Any(v => v.DisplayStatus == VideoDisplayStatus.Failed);
        if (!hasFailedJobs) return;

        try
        {
            var response = await Api.GetAsync<ApiResult<UserProfileDTO>>("users/me");
            if (response is { IsSuccess: true, Data: not null })
                AppState.CurrentUser = response.Data;
        }
        catch
        {
            Snackbar.Add("Lỗi kết nối. Vui lòng thử lại.", Severity.Error);
        }
    }

    private void StartAutoRefreshIfNeeded()
    {
        _refreshTimer?.Dispose();
        if (!_hasActiveJobs) return;

        _refreshTimer = new System.Threading.Timer(async _ =>
        {
            await InvokeAsync(async () =>
            {
                await LoadVideosAsync();
                if (!_hasActiveJobs)
                {
                    _refreshTimer?.Dispose();
                    _refreshTimer = null;
                }
            });
        }, null, TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(5));
    }

    private async Task CopyLinkAsync(VideoProjectDto video)
    {
        if (string.IsNullOrEmpty(video.LatestJob?.OutputUrl)) return;

        try
        {
            await JS.InvokeVoidAsync("navigator.clipboard.writeText", video.LatestJob.OutputUrl);
            Snackbar.Add("Đã sao chép link!", Severity.Success,
                cfg => cfg.VisibleStateDuration = 2000);
        }
        catch
        {
            Snackbar.Add("Không thể sao chép. Hãy copy thủ công.", Severity.Warning);
        }
    }

    // ✅ IAsyncDisposable — dispose Timer đúng cách
    public async ValueTask DisposeAsync()
    {
        AppState.OnChange -= StateHasChanged;

        if (_refreshTimer is not null)
        {
            await _refreshTimer.DisposeAsync();
            _refreshTimer = null;
        }
    }
}