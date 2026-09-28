// File: Services/IThemeStorageService.cs + ThemeStorageService.cs

using Microsoft.JSInterop;

namespace frontend.Services;

public class ThemeStorageService : IThemeStorageService
{
    private const string STORAGE_KEY = "saas_dark_mode";
    private readonly IJSRuntime _js;

    public ThemeStorageService(IJSRuntime js)
    {
        _js = js;
    }

    public async Task<bool> GetDarkModeAsync()
    {
        try
        {
            var saved = await _js.InvokeAsync<string>("localStorage.getItem", STORAGE_KEY);
            if (!string.IsNullOrEmpty(saved) && bool.TryParse(saved, out var result))
                return result;
        }
        catch
        {
            // localStorage không khả dụng — fallback về default
        }
        return true; // default dark
    }

    public async Task SetDarkModeAsync(bool isDark)
    {
        try
        {
            await _js.InvokeVoidAsync("localStorage.setItem", STORAGE_KEY, isDark.ToString());
        }
        catch
        {
            // localStorage không khả dụng — bỏ qua
        }
    }
}