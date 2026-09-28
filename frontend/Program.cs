// File: Program.cs

using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using MudBlazor.Services;
using MudBlazor;
using frontend;
using frontend.Common;
using frontend.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

var apiUrl     = builder.Configuration["URLConnectionConfig:ApiUrl"]     ?? "http://localhost:8000";
var apiVersion = builder.Configuration["URLConnectionConfig:ApiVersion"] ?? "api/v1/";
var fullBaseUrl = $"{apiUrl.TrimEnd('/')}/{apiVersion.TrimStart('/')}";
if (!fullBaseUrl.EndsWith("/")) fullBaseUrl += "/";

builder.Services.AddHttpClient<ApiService>(client =>
{
    client.BaseAddress = new Uri(fullBaseUrl);
    client.DefaultRequestHeaders.Add("Accept", "application/json");
    client.Timeout = TimeSpan.FromMinutes(30);
});

builder.Services.AddScoped<AppState>();
builder.Services.AddScoped<UserSyncService>();
builder.Services.AddScoped<IThemeStorageService, ThemeStorageService>();

builder.Services.AddMudServices(config =>
{
    config.PopoverOptions = new PopoverOptions
    {
        Duration = TimeSpan.FromMilliseconds(280),
        Delay    = TimeSpan.FromMilliseconds(20),
    };
});

builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("System.Net.Http.HttpClient", LogLevel.None);

builder.Services.AddMudBlazorResizeListener();

await builder.Build().RunAsync();