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
SUCCESS = "#16A34A"         # 成功确认色

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


# ── 按钮样式 ─────────────────────────────────────────

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


def loading_btn(text: str, icon: str = None, **kwargs) -> ft.Button:
    """加载态按钮 — 低饱和度青色，视觉上表示正在处理"""
    return ft.Button(
        text,
        icon=icon,
        style=ft.ButtonStyle(bgcolor="#A7F3D0", color=TEXT_PRIMARY),
        disabled=True,
        **kwargs,
    )


# ── 容器与布局 ───────────────────────────────────────

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


def module_card(content_controls: list, label: str = "", spacing: int = 6) -> ft.Container:
    """带可选小标题的分组卡片，用于数据处理模块等区域。"""
    controls = []
    if label:
        controls.append(
            ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY)
        )
    controls.extend(content_controls)
    return ft.Container(
        content=ft.Column(controls, spacing=spacing),
        padding=10,
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_SM,
        bgcolor=SURFACE,
    )


def make_collapsible(
    title: str,
    subtitle: str,
    content_controls: list,
    icon: str,
    initially_expanded: bool = True,
) -> ft.Container:
    """将内容包装为可折叠的卡片区域。"""
    _open = [initially_expanded]

    body = ft.Container(
        content=ft.Column(content_controls, spacing=8),
        padding=ft.Padding.only(left=SPACING_MD, right=SPACING_MD, bottom=SPACING_MD),
        visible=initially_expanded,
    )

    chevron = ft.Icon(
        ft.Icons.EXPAND_LESS if initially_expanded else ft.Icons.EXPAND_MORE,
        color=TEXT_SECONDARY,
        size=20,
    )

    def _toggle(e):
        _open[0] = not _open[0]
        body.visible = _open[0]
        chevron.name = ft.Icons.EXPAND_LESS if _open[0] else ft.Icons.EXPAND_MORE
        try:
            body.update()
            chevron.update()
        except (RuntimeError, AttributeError):
            pass

    header = ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=PRIMARY, size=18),
                ft.Column(
                    [
                        ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                        ft.Text(subtitle, size=11, color=TEXT_SECONDARY),
                    ],
                    spacing=1,
                    expand=True,
                ),
                chevron,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACING_MD, vertical=10),
        on_click=_toggle,
        ink=True,
    )

    return ft.Container(
        content=ft.Column([header, body], spacing=0),
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_MD,
        bgcolor=SURFACE,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


# ── 侧边栏 ───────────────────────────────────────────

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


def sidebar_group_label(text: str) -> ft.Container:
    """侧边栏分组标签"""
    return ft.Container(
        content=ft.Text(
            text,
            size=11,
            weight=ft.FontWeight.W_600,
            color=TEXT_SECONDARY,
        ),
        padding=ft.Padding.only(left=SPACING_MD + 4, top=SPACING_SM, bottom=SPACING_XS),
    )
