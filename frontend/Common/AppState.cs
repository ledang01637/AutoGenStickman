using frontend.Models; 
using System;

namespace frontend.Common;
public class AppState
{
    private UserProfileDTO? _currentUser;
    private bool _isLoadingUser = true; 

    public UserProfileDTO? CurrentUser
    {
        get => _currentUser;
        set
        {
            _currentUser = value;
            NotifyStateChanged();
        }
    }

    public bool IsLoggedIn => _currentUser is not null;

    public bool IsLoadingUser
    {
        get => _isLoadingUser;
        set
        {
            _isLoadingUser = value;
            NotifyStateChanged();
        }
    }

    public void UpdateCredit(int newCredit)
    {
        if (CurrentUser is null) return;
        CurrentUser.Credit = newCredit;
        NotifyStateChanged();
    }

    public void DeductCredit(int amount)
    {
        if (CurrentUser is null) return;
        CurrentUser.Credit -= amount;
        NotifyStateChanged();
    }

    public event Action? OnChange;
    private void NotifyStateChanged() => OnChange?.Invoke();

    public void Logout()
    {
        _currentUser = null;
        _isLoadingUser = false;
        NotifyStateChanged();
    }
}