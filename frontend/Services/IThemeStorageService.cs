namespace frontend.Services;

public interface IThemeStorageService
{
    Task<bool> GetDarkModeAsync();
    Task SetDarkModeAsync(bool isDark);
}