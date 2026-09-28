using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Components.Forms;
using Microsoft.Extensions.Logging;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.WebAssembly.Http;
using System.Text.Json.Serialization;


namespace frontend.Common;

public class ApiService
{
    private readonly NavigationManager _navManager;
    private readonly HttpClient _http;
    private readonly ILogger<ApiService> _logger;

    private static readonly JsonSerializerOptions _options = new()
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private static SemaphoreSlim _refreshLock = new(1, 1);
    private static bool _isRefreshing = false;

    public ApiService(HttpClient http, ILogger<ApiService> logger, NavigationManager navManager)
    {
        _http = http;
        _logger = logger;
        _navManager = navManager;
    }

    public async Task<T?> ApiAsync<T>(string url, HttpMethod httpMethod, object? body = null)
    {
        try
        {
            var request = CreateRequest(url, httpMethod, body);
            var response = await _http.SendAsync(request);

            if (response.StatusCode == HttpStatusCode.Unauthorized)
            {

                bool isRefreshed = await TryRefreshTokenAsync();

                if (isRefreshed)
                {
                    await Task.Delay(50);
                    var retryRequest = CreateRequest(url, httpMethod, body);
                    response = await _http.SendAsync(retryRequest);
                }
                else
                {

                    var errorResult = await TryParseBodyAsync<T>(response);
                    
                    _navManager.NavigateTo("/login", forceLoad: true);
                    return errorResult;
                }
            }

            return await ParseResponseAsync<T>(response);
        }
        catch 
        {
            throw;
        }
    }

    // ==========================================
    // PARSE BODY AN TOÀN — Không throw, dùng cho trường hợp lỗi
    // ==========================================
    private async Task<T?> TryParseBodyAsync<T>(HttpResponseMessage response)
    {
        try
        {
            var json = await response.Content.ReadAsStringAsync();
            if (string.IsNullOrWhiteSpace(json)) return default;
            return JsonSerializer.Deserialize<T>(json, _options);
        }
        catch
        {
            return default;
        }
    }

    // ==========================================
    // 2. REFRESH TOKEN (with concurrency guard)
    // ==========================================
    private async Task<bool> TryRefreshTokenAsync()
    {
        await _refreshLock.WaitAsync();
        try
        {
            if (_isRefreshing)
            {
                await Task.Delay(200);
                return true;
            }

            _isRefreshing = true;

            var refreshRequest = new HttpRequestMessage(HttpMethod.Post, "auth/refresh");
            refreshRequest.SetBrowserRequestCredentials(BrowserRequestCredentials.Include);

            var response = await _http.SendAsync(refreshRequest);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
        finally
        {
            _isRefreshing = false;
            _refreshLock.Release();
        }
    }

    // ==========================================
    // 3. REQUEST FACTORY
    // ==========================================
    private HttpRequestMessage CreateRequest(string url, HttpMethod method, object? body)
    {
        var request = new HttpRequestMessage(method, url.TrimStart('/'));
        request.SetBrowserRequestCredentials(BrowserRequestCredentials.Include);

        if (body != null && (method == HttpMethod.Post || method == HttpMethod.Put || method == HttpMethod.Patch))
        {
            request.Content = new StringContent(
                JsonSerializer.Serialize(body, _options),
                Encoding.UTF8,
                "application/json"
            );
        }

        return request;
    }

    // ==========================================
    // 4. RESPONSE PARSER — Luôn parse body dù lỗi
    // ==========================================
    private async Task<T?> ParseResponseAsync<T>(HttpResponseMessage response)
    {
        var responseJson = await response.Content.ReadAsStringAsync();

        // Nếu body rỗng hoàn toàn thì thôi
        if (string.IsNullOrWhiteSpace(responseJson))
        {
            if (!response.IsSuccessStatusCode)
            return default;
        }

        try
        {
            var result = JsonSerializer.Deserialize<T>(responseJson, _options);

            return result;
        }
        catch
        {
            throw;
        }
    }

    // ==========================================
    // 5. MULTIPART FORM POST
    // ==========================================
    public async Task<T?> PostFormAsync<T>(string url, object? body = null)
    {
        try
        {
            var request = new HttpRequestMessage(HttpMethod.Post, url.TrimStart('/'));
            request.SetBrowserRequestCredentials(BrowserRequestCredentials.Include);

            var multipartContent = new MultipartFormDataContent();
            if (body != null)
                AddFormFieldsRecursive(multipartContent, body);

            request.Content = multipartContent;

            var response = await _http.SendAsync(request);
            return await ParseResponseAsync<T>(response);
        }
        catch
        {
            throw;
        }
    }

    // ==========================================
    // 6. RECURSIVE FORM FIELDS BUILDER
    // ==========================================
    private static void AddFormFieldsRecursive(MultipartFormDataContent content, object obj, string prefix = "")
    {
        if (obj == null) return;

        foreach (var prop in obj.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            if (!prop.CanRead) continue;

            var value = prop.GetValue(obj);
            if (value == null) continue;

            var fieldName = string.IsNullOrEmpty(prefix) ? prop.Name : $"{prefix}.{prop.Name}";

            if (typeof(IBrowserFile).IsAssignableFrom(prop.PropertyType))
            {
                var file = (IBrowserFile)value;
                if (file.Size > 0)
                {
                    var fileContent = new StreamContent(file.OpenReadStream(maxAllowedSize: 10 * 1024 * 1024));
                    if (!string.IsNullOrEmpty(file.ContentType))
                        fileContent.Headers.ContentType = new MediaTypeHeaderValue(file.ContentType);
                    content.Add(fileContent, fieldName, file.Name ?? fieldName);
                }
                continue;
            }

            if (IsSimpleType(prop.PropertyType))
            {
                content.Add(new StringContent(value.ToString() ?? string.Empty, Encoding.UTF8, "text/plain"), fieldName);
                continue;
            }

            AddFormFieldsRecursive(content, value, fieldName);
        }
    }

    private static bool IsSimpleType(Type type) =>
        type.IsPrimitive || type == typeof(string) || type == typeof(decimal) ||
        type == typeof(DateTime) || type == typeof(DateTimeOffset) || type == typeof(TimeSpan) ||
        type == typeof(Guid) || type == typeof(bool) || type == typeof(Uri);

    // ==========================================
    // 7. CONVENIENCE METHODS
    // ==========================================
    public Task<T?> GetAsync<T>(string url) => ApiAsync<T>(url, HttpMethod.Get);
    public Task<T?> PostAsync<T>(string url, object body) => ApiAsync<T>(url, HttpMethod.Post, body);
    public Task<T?> PutAsync<T>(string url, object body) => ApiAsync<T>(url, HttpMethod.Put, body);
    public Task<T?> PatchAsync<T>(string url, object body) => ApiAsync<T>(url, HttpMethod.Patch, body);
    public Task<T?> DeleteAsync<T>(string url) => ApiAsync<T>(url, HttpMethod.Delete);
}