"""
GUI 主题常量与样式工具
浅色模式 + 青色(Cyan)点缀，简洁专业风格
"""
import flet as ft

# ── 配色方案 ──────────────────────────────────────────
BG = "#F8FAFC"              # 页面底层背景
SURFACE = "#FFFFFF"         # 卡片/容器背景
SURFACE_HIGH = "#F1F5F9"    # 悬停/选中态
PRIMARY = "#0891B2"         # 青色主色调(深一号，浅底可读)
PRIMARY_CONTAINER = "#CFFAFE"
ACCENT = "#059669"          # 翠绿(成功)
ERROR = "#DC2626"           # 错误/危险
WARNING = "#D97706"         # 警告
TEXT_PRIMARY = "#0F172A"    # 主文字
TEXT_SECONDARY = "#64748B"  # 次要文字
BORDER = "#E2E8F0"          # 边框/分隔线
SIDEBAR_BG = "#FFFFFF"      # 侧边栏(与卡片同色)
SIDEBAR_SELECTED = "#F0FDFA"

# ── 间距 (8px grid) ──────────────────────────────────
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# ── 圆角 ─────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 10

# ── 尺寸 ─────────────────────────────────────────────
SIDEBAR_WIDTH = 180
HEADER_HEIGHT = 48


def primary_btn(text: str, icon: str = None, **kwargs) -> ft.Button:
    """青色主操作按钮"""
    return ft.Button(
        text,
        icon=icon,
        style=ft.ButtonStyle(bgcolor=PRIMARY, color="#FFFFFF"),
        **kwargs,
    )


def secondary_btn(text: str, icon: str = None, **kwargs) -> ft.Button:
    """次要操作按钮"""
    return ft.Button(
        text,
        icon=icon,
        style=ft.ButtonStyle(bgcolor=SURFACE_HIGH, color=TEXT_PRIMARY),
        **kwargs,
    )


def destructive_btn(text: str, icon: str = None, **kwargs) -> ft.Button:
    """危险操作按钮"""
    return ft.Button(
        text,
        icon=icon,
        style=ft.ButtonStyle(bgcolor=ERROR, color="#FFFFFF"),
        **kwargs,
    )


def accent_btn(text: str, icon: str = None, **kwargs) -> ft.Button:
    """强调操作按钮(应用配置等)"""
    return ft.Button(
        text,
        icon=icon,
        style=ft.ButtonStyle(bgcolor=PRIMARY_CONTAINER, color=TEXT_PRIMARY),
        **kwargs,
    )


def card_container(content, **kwargs) -> ft.Container:
    """卡片容器样式"""
    defaults = dict(
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_LG,
        padding=SPACING_LG,
    )
    defaults.update(kwargs)
    return ft.Container(content=content, **defaults)


def section_title(text: str) -> ft.Text:
    """区域标题"""
    return ft.Text(text, size=18, weight=ft.FontWeight.W_600, color=PRIMARY)


def sidebar_item(label: str, icon: str, selected: bool = False) -> ft.Container:
    """侧边栏导航项"""
    bg = SIDEBAR_SELECTED if selected else "transparent"
    text_color = PRIMARY if selected else TEXT_SECONDARY
    icon_color = PRIMARY if selected else TEXT_SECONDARY
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=icon_color, size=20),
                ft.Text(label, color=text_color, size=14, weight=ft.FontWeight.W_500),
            ],
            spacing=SPACING_SM,
        ),
        bgcolor=bg,
        border_radius=RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=SPACING_MD, vertical=10),
        on_click=None,  # 由外部绑定
        ink=True,
    )
