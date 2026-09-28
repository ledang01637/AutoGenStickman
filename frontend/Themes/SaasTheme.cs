// File: Themes/SaasTheme.cs

using MudBlazor;

namespace frontend.Themes;

public static class SaasTheme
{
    public static readonly MudTheme Instance = new()
    {
        PaletteLight = new PaletteLight()
        {
            Primary          = "#4169E1",
            Secondary        = "#50C878",
            AppbarBackground = "#ffffff",
            AppbarText       = "#1e293b",
            DrawerBackground = "#f4f7fb",
            DrawerText       = "#475569",
            DrawerIcon       = "#64748b",
            Background       = "#f8fafc",
            Surface          = "#ffffff",
            TextPrimary      = "#1e293b",
            TextSecondary    = "#64748b",
            Divider          = "#e2e8f0",
            DividerLight     = "#f1f5f9",
        },
        PaletteDark = new PaletteDark()
        {
            Primary          = "#4169E1",
            Secondary        = "#50C878",
            AppbarBackground = "rgba(21, 24, 33, 0.92)",
            AppbarText       = "#e2e8f0",
            DrawerBackground = "#151821",
            DrawerText       = "#94a3b8",
            DrawerIcon       = "#64748b",
            Background       = "#0f111a",
            Surface          = "#1a1d27",
            TextPrimary      = "#e2e8f0",
            TextSecondary    = "#94a3b8",
            Divider          = "#2d3142",
            DividerLight     = "#1e2235",
        },
        Typography = new Typography()
        {
            Default =
            {
                FontFamily = ["Inter", "Be Vietnam Pro", "Helvetica", "Arial", "sans-serif"],
                FontSize   = "0.875rem",
                FontWeight = "400"
            },
            H5 =
            {
                FontFamily = ["Inter", "Be Vietnam Pro", "Helvetica", "Arial", "sans-serif"],
                FontWeight = "700"
            },
            Subtitle1 =
            {
                FontFamily = ["Inter", "Be Vietnam Pro", "Helvetica", "Arial", "sans-serif"],
                FontWeight = "600"
            }
        }
    };
}