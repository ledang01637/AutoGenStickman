using MudBlazor;
using frontend.Models;

namespace frontend.Common;

public class UserSyncService
{
    private readonly ApiService _api;
    private readonly AppState _appState;

    public UserSyncService(ApiService api, AppState appState)
    {
        _api = api;
        _appState = appState;
    }

    public async Task SyncUserAsync(int deductedCredits = 0)
    {
        try
        {
            var response = await _api.GetAsync<ApiResult<UserProfileDTO>>("users/me");

            // Sync thành công → cập nhật profile mới từ server
            if (response is { IsSuccess: true, Data: not null })
            {
                _appState.CurrentUser = response.Data;
                return;
            }

            // API trả về fail → fallback rollback credit nếu có
            RollbackCreditIfNeeded(deductedCredits);
        }
        catch
        {
            RollbackCreditIfNeeded(deductedCredits);
        }
    }

    // Khôi phục credit khi sync thất bại — tránh trừ oan của user
    private void RollbackCreditIfNeeded(int deductedCredits)
    {
        if (_appState.CurrentUser is not null && deductedCredits > 0)
        {
            _appState.UpdateCredit(_appState.CurrentUser.Credit + deductedCredits);
        }
    }
}