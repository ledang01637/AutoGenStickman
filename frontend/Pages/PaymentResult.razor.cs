using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.WebUtilities;
using MudBlazor;
using frontend.Common;
using frontend.Models;
using Microsoft.JSInterop;

namespace frontend.Pages;

public partial class PaymentResult : ComponentBase, IDisposable
{
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private NavigationManager Nav { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;
    [Inject] private UserSyncService UserSync { get; set; } = default!;
    [Inject] private IJSRuntime JS { get; set; } = default!;

    private long _orderCode;
    private string? _payOsCode;
    private bool _payOsCancelled;
    private string _returnUrl = "/";

    private ResultState _state = ResultState.Polling;
    private int _attempts;
    private const int _maxAttempts = 12;       // 12 lần × 2.5s = 30s
    private const int _pollIntervalMs = 2500;
    private string _errorMessage = "Đã có lỗi xảy ra trong quá trình thanh toán.";

    private CancellationTokenSource? _cts;

    public enum ResultState
    {
        Polling,
        Success,
        Cancelled,
        Failed,
        Timeout
    }

    protected override async Task OnInitializedAsync()
    {
        // Parse query string từ URL PayOS redirect về
        var uri = Nav.ToAbsoluteUri(Nav.Uri);
        var query = QueryHelpers.ParseQuery(uri.Query);

        // orderCode là public identifier, an toàn lộ ra URL
        if (!query.TryGetValue("orderCode", out var orderCodeStr)
            || !long.TryParse(orderCodeStr, out _orderCode))
        {
            _state = ResultState.Failed;
            _errorMessage = "Thiếu thông tin đơn hàng từ cổng thanh toán.";
            return;
        }
        

        // PayOS chuẩn: code=00 thành công, cancel=true nếu user hủy
        query.TryGetValue("code", out var code);
        _payOsCode = code.ToString();

        query.TryGetValue("cancel", out var cancelStr);
        _payOsCancelled = string.Equals(
            cancelStr.ToString(), "true", StringComparison.OrdinalIgnoreCase
        );

        _returnUrl = await JS.InvokeAsync<string?>("localStorage.getItem", "payment_return_url") ?? "/";
        await JS.InvokeVoidAsync("localStorage.removeItem", "payment_return_url");

        // PayOS đã báo cancel ngay từ URL → skip polling, hiển thị luôn
        if (_payOsCancelled)
        {
            _state = ResultState.Cancelled;
            return;
        }

        // Bắt đầu poll backend xác nhận webhook đã xử lý xong
        _cts = new CancellationTokenSource();
        await PollOrderStatusAsync(_cts.Token);
    }

    // Poll backend cho tới khi có kết quả final hoặc hết số lần thử
    private async Task PollOrderStatusAsync(CancellationToken ct)
    {
        while (_attempts < _maxAttempts && !ct.IsCancellationRequested)
        {
            _attempts++;
            StateHasChanged();

            try
            {
                // Query bằng order_code (public) — backend tự check ownership qua JWT
                var result = await Api.GetAsync<ApiResult<PaymentOrderDto>>(
                    $"payments/by-code/{_orderCode}"
                );

                if (result?.IsSuccess == true && result.Data is not null)
                {
                    var status = result.Data.Status?.ToUpperInvariant();
                    switch (status)
                    {
                        case "PAID":
                            _state = ResultState.Success;
                            await UserSync.SyncUserAsync();
                            return;

                        case "CANCELLED":
                            _state = ResultState.Cancelled;
                            return;

                        case "FAILED":
                            _state = ResultState.Failed;
                            _errorMessage = result.Message ?? "Thanh toán thất bại.";
                            return;

                        case "PENDING":
                            // Webhook chưa về — tiếp tục poll
                            break;

                        default:
                            _state = ResultState.Failed;
                            _errorMessage = $"Trạng thái không xác định: {status}";
                            return;
                    }
                }
            }
            catch
            {
                Snackbar.Add("Lỗi kết nối", Severity.Error);
            }

            try
            {
                await Task.Delay(_pollIntervalMs, ct);
            }
            catch (TaskCanceledException)
            {
                return;
            }
        }

        // Hết lần thử mà vẫn PENDING → fallback timeout state
        _state = ResultState.Timeout;
        StateHasChanged();
    }
    
    // Cho phép user thử lại sau khi timeout
    private async Task CheckAgain()
    {
        _state = ResultState.Polling;
        _attempts = 0;
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();
        await PollOrderStatusAsync(_cts.Token);
    }

    private void GoHome() => Nav.NavigateTo("/");
    private void GoBack() => Nav.NavigateTo(_returnUrl);

    public void Dispose()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        GC.SuppressFinalize(this);
    }
}