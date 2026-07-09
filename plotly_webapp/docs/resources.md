# Resources

Use this file as the single runtime source of truth for external links.

| Resource | URL | When to use |
|---|---|---|
| Figma Design System | https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP-%E2%80%93-Design-System-by-Significa | Visual reference for DS structure, spacing, and behavior. The "Detail Page" template is the target layout. |
| Dash Core Components | https://dash.plotly.com/dash-core-components | First fallback when a needed UI element does not exist in this DS. |
| Dash Mantine Components | https://www.dash-mantine-components.com/ | Last-resort UI framework when DS + Dash Core cannot satisfy a requirement. |
| Lucide Icons | https://lucide.dev/icons/ | Find icon names to use with DashIconify. |

Priority order for implementation decisions:

1. Reuse existing DS components first.
2. If missing, use Dash Core Components.
3. If still missing, use Dash Mantine Components.
4. Avoid arbitrary third-party UI libraries.
