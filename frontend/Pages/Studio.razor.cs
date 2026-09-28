// File: Pages/Studio.razor.cs

using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.WebAssembly.Http;
using MudBlazor;
using frontend.Common;
using frontend.Models;

namespace frontend.Pages;

public partial class Studio : ComponentBase, IAsyncDisposable
{
    // ═══════════════════════════════════════════════════════════
    // 1. INJECT
    // ═══════════════════════════════════════════════════════════
    [Inject] private ApiService Api { get; set; } = default!;
    [Inject] private IHttpClientFactory HttpFactory { get; set; } = default!;
    [Inject] private ISnackbar Snackbar { get; set; } = default!;
    [Inject] private AppState AppState { get; set; } = default!;
    [Inject] private NavigationManager NavManager { get; set; } = default!;
    [Inject] private UserSyncService UserSync { get; set; } = default!;

    // ═══════════════════════════════════════════════════════════
    // 2. FORM STATE — CORE
    // ═══════════════════════════════════════════════════════════
    private string _topic = string.Empty;
    private string _title = string.Empty;
    private float _selectedMinutes = 0.5f;
    private bool _formValidated = false;
    private bool _isSubmitting = false;
    private bool _showPlayer = false;

    // ═══════════════════════════════════════════════════════════
    // 3. FORM STATE — ADVANCED (PRO+)
    // ═══════════════════════════════════════════════════════════
    private bool _showAdvanced = false;
    private string _mainCharacter = "a stickman wearing a tie and round glasses";
    private string _selectedPace = "balanced";
    private string _selectedStoryStructure = "problem_solve";
    private string _selectedTone = "serious";
    private bool _useBestModel = false;
    private bool _useColorImage = false;
    private bool _isSpeed = false;
    private string _selectedVoice = "hn_female_ngochuyen_full_48k-fhg";
    private string _selectedRatio = "9:16";

    // ═══════════════════════════════════════════════════════════
    // 4. PROCESSING STATE
    // ═══════════════════════════════════════════════════════════
    private bool _isProcessing = false;
    private bool _isCompleted = false;
    private bool _isError = false;
    private string _jobId = string.Empty;
    private int _progress = 0;
    private string _statusMessage = "Đang khởi động...";
    private string _errorMessage = string.Empty;
    private string _videoUrl = "#";
    private int _currentStep = 0;
    private int _deductedCredits = 0;

    // ═══════════════════════════════════════════════════════════
    // 5. UPGRADE DIALOG
    // ═══════════════════════════════════════════════════════════
    private bool _showUpgradeDialog = false;
    private string _upgradeFeatureName = string.Empty;
    private string _upgradeRequiredPlan = "PRO";

    // ═══════════════════════════════════════════════════════════
    // 6. COST ESTIMATE
    // ═══════════════════════════════════════════════════════════
    private EstimateCostData? _costEstimate;
    private bool _isEstimating = false;
    private System.Timers.Timer? _estimateDebounceTimer;
    private int _currentEstimateRequestId = 0;
    private const int DEBOUNCE_MS = 400;

    // ═══════════════════════════════════════════════════════════
    // 7. PLAN HELPERS (computed properties)
    // ═══════════════════════════════════════════════════════════
    private string CurrentPlan => AppState.CurrentUser?.Plan ?? "FREE";
    private float MaxMinutes => PlanFeatures.GetMaxMinutes(CurrentPlan);
    private bool CanCustomizeCharacter => PlanFeatures.CanCustomizeCharacter(CurrentPlan);
    private bool CanCustomizePace => PlanFeatures.CanCustomizePace(CurrentPlan);
    private bool CanUseFastCut => PlanFeatures.CanUseFastCut(CurrentPlan);
    private bool CanCustomizeStoryStructure => PlanFeatures.CanCustomizeStoryStructure(CurrentPlan);
    private bool CanCustomizeVoice => PlanFeatures.CanCustomizeVoice(CurrentPlan);
    private bool CanUseBestModel => PlanFeatures.CanUseBestModel(CurrentPlan);
    private bool CanUseColorImage => PlanFeatures.CanUseColorImage(CurrentPlan);
    private bool CanChooseRenderTier => PlanFeatures.CanChooseRenderTier(CurrentPlan);

    private bool HasAnyAdvancedFeature =>
        CanCustomizeCharacter || CanCustomizePace || CanCustomizeStoryStructure || CanUseBestModel || CanChooseRenderTier;

    // ═══════════════════════════════════════════════════════════
    // 7b. DURATION SLIDER — map giá trị phút không liên tục (0.5/1/3/5) sang index
    // ═══════════════════════════════════════════════════════════

    /// Danh sách (phút, label đầy đủ, label ngắn cho tick mark) — phụ thuộc plan
    private List<(float Minutes, string Label, string ShortLabel)> AllowedDurations
    {
        get
        {
            var list = new List<(float Minutes, string Label, string ShortLabel)>
            {
                (0.5f, "0.5 phút — Ngắn (30s)", "30s")
            };

            if (MaxMinutes >= 1f) list.Add((1.0f, "1 phút — Tiêu chuẩn", "1p"));
            if (MaxMinutes >= 3f) list.Add((2.0f, "2 phút — Dài", "2p"));
            if (MaxMinutes >= 5f) list.Add((3.0f, "3 phút — Rất dài", "3p"));

            return list;
        }
    }

    /// Tick mark labels cho MudSlider — hiển thị "30s", "1p", "2p", "3p"
    private string[] DurationTickLabels => AllowedDurations.Select(d => d.ShortLabel).ToArray();

    /// Label ngắn của lựa chọn hiện tại — dùng cho badge trên duration header
    private string SelectedDurationLabel => AllowedDurations.Count > 0
        ? AllowedDurations[DurationIndex].ShortLabel
        : "30s";

    /// Index hiện tại trên slider, suy ra từ _selectedMinutes
    private int DurationIndex
    {
        get
        {
            var idx = AllowedDurations.FindIndex(d => Math.Abs(d.Minutes - _selectedMinutes) < 0.01f);
            return idx >= 0 ? idx : 0;
        }
    }

    /// Slider trả về index — map ngược sang _selectedMinutes
    private void OnDurationIndexChanged(int newIndex)
    {
        if (newIndex < 0 || newIndex >= AllowedDurations.Count) return;

        var newMinutes = AllowedDurations[newIndex].Minutes;
        if (Math.Abs(newMinutes - _selectedMinutes) < 0.01f) return;

        _selectedMinutes = newMinutes;
        ScheduleEstimate();
    }

    // ═══════════════════════════════════════════════════════════
    // 8. CREDIT — derived from estimate
    // ═══════════════════════════════════════════════════════════
    private int _userCredits => AppState.CurrentUser?.Credit ?? 0;
    private int CreditCost => _costEstimate?.CostCredits ?? 0;
    private int EstimatedScenes => _costEstimate?.TotalScenes ?? 0;
    private bool CanAffordEstimate => _costEstimate?.CanAfford ?? true;

    private readonly string[] _processingSteps =
    {
        "Phân tích", "Kịch bản", "AI Vẽ", "Kết xuất", "Xuất file",
    };

    private CancellationTokenSource _cts = new();

    // ═══════════════════════════════════════════════════════════
    // 9. API MODELS
    // ═══════════════════════════════════════════════════════════
    private sealed class GenerateVideoData
    {
        [JsonPropertyName("project_id")] public string ProjectId { get; set; } = string.Empty;
        [JsonPropertyName("job_id")] public string JobId { get; set; } = string.Empty;
        [JsonPropertyName("cost_credits")] public int CostCredits { get; set; }
        [JsonPropertyName("status")] public string Status { get; set; } = string.Empty;
    }

    private sealed class SsePayload
    {
        [JsonPropertyName("progress")] public int Progress { get; set; }
        [JsonPropertyName("message")] public string Message { get; set; } = string.Empty;
        [JsonPropertyName("is_done")] public bool IsDone { get; set; }
        [JsonPropertyName("is_error")] public bool IsError { get; set; }
        [JsonPropertyName("video_url")] public string? VideoUrl { get; set; }
    }

    private static readonly JsonSerializerOptions _json = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    // ═══════════════════════════════════════════════════════════
    // 10. LIFECYCLE
    // ═══════════════════════════════════════════════════════════
    protected override async Task OnInitializedAsync()
    {
        AppState.OnChange += OnAppStateChanged;
        EnsureSelectionsAreValid();
        await FetchCostEstimateAsync();
    }

    private void EnsureSelectionsAreValid()
    {
        // Plan downgrade guard: clamp về mức cao nhất mà plan hiện tại cho phép
        if (_selectedMinutes > MaxMinutes)
            _selectedMinutes = MaxMinutes;

        var allowedPaces = PlanFeatures.GetAllowedPaces(CurrentPlan);
        if (!allowedPaces.Contains(_selectedPace))
            _selectedPace = allowedPaces[0];

        var allowedStructures = PlanFeatures.GetAllowedStructures(CurrentPlan);
        if (!allowedStructures.Contains(_selectedStoryStructure))
            _selectedStoryStructure = allowedStructures[0];

        var allowedTones = PlanFeatures.GetAllowedTones(CurrentPlan);
        if (!allowedTones.Contains(_selectedTone))
            _selectedTone = allowedTones[0];
    }

    private async void OnAppStateChanged()
    {
        await InvokeAsync(async () =>
        {
            EnsureSelectionsAreValid();
            await FetchCostEstimateAsync();
            StateHasChanged();
        });
    }

    // ═══════════════════════════════════════════════════════════
    // 11. UPGRADE DIALOG
    // ═══════════════════════════════════════════════════════════
    private void ShowUpgradeDialog(string featureName, string requiredPlan = "PRO")
    {
        _upgradeFeatureName = featureName;
        _upgradeRequiredPlan = requiredPlan;
        _showUpgradeDialog = true;
    }

    private void CloseUpgradeDialog() => _showUpgradeDialog = false;

    private void NavigateToPricing()
    {
        _showUpgradeDialog = false;
        NavManager.NavigateTo("/pricing");
    }

    // ═══════════════════════════════════════════════════════════
    // 12. LOCKED FEATURE HANDLERS
    // ═══════════════════════════════════════════════════════════
    private void OnCharacterFieldClick()
    {
        if (!CanCustomizeCharacter)
            ShowUpgradeDialog("Tuỳ chỉnh nhân vật chính");
    }

    private void OnPaceFieldClick()
    {
        if (!CanCustomizePace)
            ShowUpgradeDialog("Tuỳ chỉnh nhịp điệu video");
    }

    private void OnFastCutSelected()
    {
        if (_selectedPace == "fast_cut" && !CanUseFastCut)
        {
            _selectedPace = "balanced";
            ShowUpgradeDialog("Fast Cut (18 cảnh/phút)", "ULTRA");
        }
    }

    private void OnStoryStructureFieldClick()
    {
        if (!CanCustomizeStoryStructure)
            ShowUpgradeDialog("Cấu trúc câu chuyện");
    }

    private void OnVoiceFieldClick()
    {
        if (!CanCustomizeVoice)
            ShowUpgradeDialog("Giọng đọc");
    }

    private void OnBestModelRowClick()
    {
        if (!CanUseBestModel)
        {
            ShowUpgradeDialog("Mô hình AI tốt nhất");
            return;
        }

        _useBestModel = !_useBestModel;
    }

    private void OnColorImageRowClick()
    {
        if (!CanUseColorImage)
        {
            ShowUpgradeDialog("Ảnh có màu sắc");
            return;
        }

        _useColorImage = !_useColorImage;
    }

    private void OnSpeedRowClick()
    {
        if (!CanChooseRenderTier)
        {
            ShowUpgradeDialog("Tuỳ chỉnh tốc độ render");
            return;
        }

        _isSpeed = !_isSpeed;
    }

    private void OnTopicChanged(string newValue)
    {
        _topic = newValue;

        if (_formValidated && !string.IsNullOrWhiteSpace(newValue))
        {
            _formValidated = false;
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 13. COST ESTIMATE (debounced)
    // ═══════════════════════════════════════════════════════════
    private void ScheduleEstimate()
    {
        _estimateDebounceTimer?.Stop();
        _estimateDebounceTimer?.Dispose();

        _estimateDebounceTimer = new System.Timers.Timer(DEBOUNCE_MS)
        {
            AutoReset = false,
        };
        _estimateDebounceTimer.Elapsed += async (_, _) =>
        {
            await InvokeAsync(FetchCostEstimateAsync);
        };
        _estimateDebounceTimer.Start();
    }

    private async Task FetchCostEstimateAsync()
    {
        var requestId = ++_currentEstimateRequestId;
        _isEstimating = true;
        StateHasChanged();

        try
        {
            var queryParams = new List<string>
            {
                $"minutes={_selectedMinutes.ToString(System.Globalization.CultureInfo.InvariantCulture)}",
            };

            if (CanCustomizePace)
                queryParams.Add($"pace={_selectedPace}");

            var url = $"videos/estimate-cost?{string.Join("&", queryParams)}";
            var result = await Api.GetAsync<ApiResult<EstimateCostData>>(url);

            if (requestId != _currentEstimateRequestId) return;

            if (result is { IsSuccess: true, Data: not null })
            {
                _costEstimate = result.Data;

                if (_costEstimate.PaceLocked)
                    _selectedPace = _costEstimate.EffectivePace;
            }
            else
            {
                _costEstimate = null;
            }
        }
        catch
        {
            if (requestId == _currentEstimateRequestId)
                _costEstimate = null;
        }
        finally
        {
            if (requestId == _currentEstimateRequestId)
            {
                _isEstimating = false;
                StateHasChanged();
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 14. FIELD CHANGE HANDLERS
    // ═══════════════════════════════════════════════════════════
    private async Task OnPaceChanged(string newPace)
    {
        if (!PlanFeatures.GetAllowedPaces(CurrentPlan).Contains(newPace))
        {
            var required = PlanFeatures.GetRequiredPlanForPace(newPace);
            ShowUpgradeDialog($"Nhịp điệu {newPace}", required);

            var currentPace = _selectedPace;
            _selectedPace = string.Empty;
            await InvokeAsync(StateHasChanged);
            await Task.Delay(1);
            _selectedPace = currentPace;
            await InvokeAsync(StateHasChanged);
            return;
        }

        _selectedPace = newPace;
        ScheduleEstimate();
    }

    private bool ValidateAgainstPlan()
    {
        if (_selectedMinutes > MaxMinutes)
        {
            Snackbar.Add(
                $"Gói {PlanFeatures.GetDisplayName(CurrentPlan)} chỉ cho phép video tối đa {MaxMinutes} phút.",
                Severity.Warning
            );
            return false;
        }
        return true;
    }

    // ═══════════════════════════════════════════════════════════
    // 15. START GENERATION
    // ═══════════════════════════════════════════════════════════
    private async Task StartGenerationAsync()
    {
        _formValidated = true;

        if (string.IsNullOrWhiteSpace(_topic))
        {
            Snackbar.Add("Vui lòng nhập chủ đề video.", Severity.Warning);
            return;
        }

        if (!ValidateAgainstPlan()) return;

        if (_costEstimate is null || _isEstimating)
            await FetchCostEstimateAsync();

        if (_costEstimate is null)
        {
            Snackbar.Add("Không thể ước tính chi phí. Vui lòng thử lại.", Severity.Error);
            return;
        }

        if (!_costEstimate.CanAfford)
        {
            Snackbar.Add(
                $"Không đủ Credit. Cần {_costEstimate.CostCredits}, hiện có {_costEstimate.CurrentBalance}.",
                Severity.Error
            );
            return;
        }

        await _cts.CancelAsync();
        _cts.Dispose();
        _cts = new CancellationTokenSource();

        _isSubmitting = true;
        _errorMessage = string.Empty;
        StateHasChanged();

        try
        {
            var payload = new Dictionary<string, object?>
            {
                ["title"] = string.IsNullOrWhiteSpace(_title) ? _topic.Trim() : _title.Trim(),
                ["topic"] = _topic.Trim(),
                ["minutes"] = _selectedMinutes,
                ["tone"] = _selectedTone,
                ["story_structure"] = _selectedStoryStructure,
                ["pace"] = _selectedPace,
                ["use_best_model"] = _useBestModel,
                ["use_color_image"] = _useColorImage,
                ["is_speed"] = _isSpeed,
                ["main_character"] = _mainCharacter.Trim(),
                ["voice_code"] = _selectedVoice,
                ["ratio"] = _selectedRatio,
                ["render_type"] = "static"
            };

            var result = await Api.PostAsync<ApiResult<GenerateVideoData>>("videos/generate", payload);

            if (result is not { IsSuccess: true } || result.Data is null)
            {
                ShowError(result?.Message ?? "Phản hồi máy chủ không hợp lệ.");
                _isSubmitting = false;
                StateHasChanged();
                return;
            }

            var jobId = result.Data.JobId;
            if (string.IsNullOrEmpty(jobId))
            {
                ShowError("Máy chủ không trả về Job ID.");
                return;
            }

            if (AppState.CurrentUser is not null)
            {
                AppState.DeductCredit(result.Data.CostCredits);
                _deductedCredits = result.Data.CostCredits;
            }

            _jobId = jobId;
            _progress = 0;
            _currentStep = 0;
            _statusMessage = "Đang khởi tạo hàng đợi...";
            _isSubmitting = false;
            _isProcessing = true;
            StateHasChanged();

            await ListenToProgressAsync(_cts.Token);
        }
        catch (OperationCanceledException) { }
        catch
        {
            if (_deductedCredits > 0)
            {
                AppState.UpdateCredit(AppState.CurrentUser!.Credit + _deductedCredits);
                ShowError($"Lỗi kết nối");
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 16. SSE LISTENER
    // ═══════════════════════════════════════════════════════════
    private async Task ListenToProgressAsync(CancellationToken ct)
    {
        try
        {
            var http = HttpFactory.CreateClient("ApiService");
            var request = new HttpRequestMessage(HttpMethod.Get, $"videos/progress/{_jobId}");
            request.SetBrowserRequestCredentials(BrowserRequestCredentials.Include);
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("text/event-stream"));
            request.SetBrowserResponseStreamingEnabled(true);

            using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);

            if (!response.IsSuccessStatusCode)
            {
                var err = await response.Content.ReadAsStringAsync(ct);
                ShowError(
                    userMessage:     "Không thể theo dõi tiến trình. Vui lòng kiểm tra Lịch Sử sau ít phút.",
                    technicalDetail: $"SSE HTTP {(int)response.StatusCode}: {err}",
                    syncUser:        true
                );
                return;
            }

            await using var stream = await response.Content.ReadAsStreamAsync(ct);
            using var reader = new System.IO.StreamReader(stream);

            string? line;
            while ((line = await reader.ReadLineAsync(ct)) != null)
            {
                if (!line.StartsWith("data:", StringComparison.OrdinalIgnoreCase))
                    continue;

                var raw = line["data:".Length..].Trim();
                if (string.IsNullOrWhiteSpace(raw)) continue;

                SsePayload? payload;
                try { payload = JsonSerializer.Deserialize<SsePayload>(raw, _json); }
                catch { continue; }

                if (payload is null) continue;

                _progress = Math.Clamp(payload.Progress, 0, 100);
                _statusMessage = payload.Message ?? string.Empty;
                _currentStep = MapProgressToStep(_progress);
                StateHasChanged();

                if (payload.IsError)
                {
                    ShowError(
                        userMessage:     "Tạo video thất bại. Credit đã được hoàn lại nếu có.",
                        technicalDetail: $"Job {_jobId} failed: {payload.Message}",
                        syncUser:        true
                    );
                    return;
                }

                if (payload.IsDone)
                {
                    _progress         = 100;
                    _currentStep      = _processingSteps.Length;
                    _videoUrl         = payload.VideoUrl ?? "#";
                    _deductedCredits  = 0;
                    await UserSync.SyncUserAsync();
                    TransitionTo(completed: true);
                    return;
                }
            }

            if (_isProcessing)
            {
                ShowError(
                    userMessage:     "Mất kết nối. Video có thể đã hoàn thành — hãy kiểm tra Lịch Sử.",
                    technicalDetail: "SSE stream ended unexpectedly",
                    syncUser:        true
                );
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception ex)
        {
            ShowError(
                userMessage:     "Có lỗi xảy ra khi theo dõi tiến trình. Vui lòng kiểm tra Lịch Sử.",
                technicalDetail: $"SSE exception: {ex}",
                syncUser:        true
            );
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 17. HELPERS
    // ═══════════════════════════════════════════════════════════
    private int MapProgressToStep(int p) => p switch
    {
        < 15 => 0,
        < 35 => 1,
        < 60 => 2,
        < 85 => 3,
        _ => 4,
    };

    private void ShowError(
        string userMessage,
        string? technicalDetail = null,
        bool syncUser = false)
    {
        _errorMessage = userMessage;
        Snackbar.Add(userMessage, Severity.Error);

        if (!string.IsNullOrWhiteSpace(technicalDetail))
            Console.Error.WriteLine($"[Studio] {technicalDetail}");

        TransitionTo(error: true);

        if (syncUser)
            _ = SyncWithRetryAsync(_deductedCredits);
    }

    private void TransitionTo(bool completed = false, bool error = false)
    {
        _isProcessing = false;
        _isSubmitting = false;
        _isCompleted = completed;
        _isError = error;
        StateHasChanged();
    }

    private async Task SyncWithRetryAsync(int deductedCredits, int maxAttempts = 5)
    {
        var creditBeforeSync = AppState.CurrentUser?.Credit ?? 0;

        for (int i = 0; i < maxAttempts; i++)
        {
            await Task.Delay(i == 0 ? 1000 : 2000);
            await UserSync.SyncUserAsync(deductedCredits);

            var creditAfterSync = AppState.CurrentUser?.Credit ?? 0;

            if (creditAfterSync > creditBeforeSync)
                break;
        }
    }

    private async Task ResetStudio()
    {
        _isProcessing = false;
        _isCompleted = false;
        _isError = false;
        _isSubmitting = false;
        _formValidated = false;
        _progress = 0;
        _currentStep = 0;
        _statusMessage = "Đang khởi động...";
        _errorMessage = string.Empty;
        _jobId = string.Empty;
        _videoUrl = "#";

        await FetchCostEstimateAsync();
        StateHasChanged();
    }

    // ═══════════════════════════════════════════════════════════
    // 18. DISPOSE
    // ═══════════════════════════════════════════════════════════
    public async ValueTask DisposeAsync()
    {
        AppState.OnChange -= OnAppStateChanged;
        _estimateDebounceTimer?.Stop();
        _estimateDebounceTimer?.Dispose();
        await _cts.CancelAsync();
        _cts.Dispose();
    }
}