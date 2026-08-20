"""GUI 主题常量与样式工具。

视觉语言以低饱和中性色为底，仅在主操作、当前导航和状态反馈中使用青色。
组件尺寸和交互状态集中在这里，避免各页面形成不同的控件风格。
"""
import flet as ft

# ── 配色方案 ──────────────────────────────────────────
BG = "#F4F7F9"              # 页面底层背景
SURFACE = "#FFFFFF"         # 卡片/容器背景
SURFACE_LOW = "#F8FAFB"     # 侧栏、工具栏等次级表面
SURFACE_HIGH = "#EEF3F5"    # 悬停/选中态
PRIMARY = "#087F8C"         # 主操作色，兼顾白色文字对比度
PRIMARY_HOVER = "#076D78"
PRIMARY_CONTAINER = "#DDF3F3"
PRIMARY_CONTAINER_STRONG = "#C8E9E9"
ERROR = "#C73737"           # 错误/危险
ERROR_HOVER = "#A92E2E"
WARNING = "#A86008"         # 警告
TEXT_PRIMARY = "#16272E"    # 主文字
TEXT_SECONDARY = "#52666E"  # 次要文字
TEXT_TERTIARY = "#73868D"   # 辅助信息
BORDER = "#D7E1E4"          # 边框/分隔线
BORDER_STRONG = "#C3D0D4"
SIDEBAR_BG = SURFACE_LOW
SIDEBAR_SELECTED = PRIMARY_CONTAINER
SUCCESS = "#207A50"         # 成功确认色

# ── 间距 (8px grid) ──────────────────────────────────
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# ── 圆角 ─────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 9
RADIUS_LG = 12

# ── 尺寸 ─────────────────────────────────────────────
SIDEBAR_WIDTH = 204
CONTROL_HEIGHT = 38


def _button_shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=RADIUS_MD)


def _button_style(
    *,
    bgcolor: str,
    color: str,
    hover_bgcolor: str,
    border_color: str | None = None,
) -> ft.ButtonStyle:
    states = ft.ControlState
    return ft.ButtonStyle(
        bgcolor={
            states.DEFAULT: bgcolor,
            states.HOVERED: hover_bgcolor,
            states.PRESSED: hover_bgcolor,
            states.DISABLED: SURFACE_HIGH,
        },
        color={
            states.DEFAULT: color,
            states.DISABLED: TEXT_TERTIARY,
        },
        overlay_color={
            states.HOVERED: "#12000000",
            states.PRESSED: "#1F000000",
        },
        side=ft.BorderSide(1, border_color) if border_color else None,
        shape=_button_shape(),
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
        icon_size=18,
        elevation=0,
        animation_duration=160,
    )


# ── 按钮样式 ─────────────────────────────────────────

def primary_btn(text: str, icon: str | None = None, **kwargs) -> ft.Button:
    """主操作按钮。"""
    kwargs.setdefault("height", CONTROL_HEIGHT)
    return ft.Button(
        text,
        icon=icon,
        style=_button_style(
            bgcolor=PRIMARY,
            color="#FFFFFF",
            hover_bgcolor=PRIMARY_HOVER,
        ),
        **kwargs,
    )


def secondary_btn(text: str, icon: str | None = None, **kwargs) -> ft.Button:
    """次要操作按钮。"""
    kwargs.setdefault("height", CONTROL_HEIGHT)
    return ft.Button(
        text,
        icon=icon,
        style=_button_style(
            bgcolor=SURFACE,
            color=TEXT_PRIMARY,
            hover_bgcolor=SURFACE_HIGH,
            border_color=BORDER_STRONG,
        ),
        **kwargs,
    )


def destructive_btn(text: str, icon: str | None = None, **kwargs) -> ft.Button:
    """危险操作按钮"""
    kwargs.setdefault("height", CONTROL_HEIGHT)
    return ft.Button(
        text,
        icon=icon,
        style=_button_style(
            bgcolor=ERROR,
            color="#FFFFFF",
            hover_bgcolor=ERROR_HOVER,
        ),
        **kwargs,
    )


def accent_btn(text: str, icon: str | None = None, **kwargs) -> ft.Button:
    """强调操作按钮(应用配置等)"""
    kwargs.setdefault("height", CONTROL_HEIGHT)
    return ft.Button(
        text,
        icon=icon,
        style=_button_style(
            bgcolor=PRIMARY_CONTAINER,
            color=PRIMARY_HOVER,
            hover_bgcolor=PRIMARY_CONTAINER_STRONG,
            border_color=PRIMARY_CONTAINER_STRONG,
        ),
        **kwargs,
    )


def loading_btn(text: str, icon: str | None = None, **kwargs) -> ft.Button:
    """加载态按钮。"""
    kwargs.setdefault("height", CONTROL_HEIGHT)
    return ft.Button(
        text,
        icon=icon,
        style=_button_style(
            bgcolor=PRIMARY_CONTAINER_STRONG,
            color=PRIMARY_HOVER,
            hover_bgcolor=PRIMARY_CONTAINER_STRONG,
        ),
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
        padding=SPACING_XL,
    )
    defaults.update(kwargs)
    return ft.Container(content=content, **defaults)


def section_title(text: str) -> ft.Text:
    """区域标题"""
    return ft.Text(
        text,
        size=20,
        weight=ft.FontWeight.W_700,
        color=TEXT_PRIMARY,
    )


def module_card(content_controls: list, label: str = "", spacing: int = 6) -> ft.Container:
    """带可选小标题的分组卡片，用于数据处理模块等区域。"""
    controls = []
    if label:
        controls.append(
            ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)
        )
    controls.extend(content_controls)
    return ft.Container(
        content=ft.Column(controls, spacing=spacing),
        padding=SPACING_MD,
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_MD,
        bgcolor=SURFACE_LOW,
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
        content=ft.Column(content_controls, spacing=SPACING_SM),
        padding=ft.Padding.only(
            left=SPACING_LG,
            right=SPACING_LG,
            bottom=SPACING_LG,
        ),
        visible=initially_expanded,
    )

    chevron = ft.Icon(
        ft.Icons.EXPAND_LESS if initially_expanded else ft.Icons.EXPAND_MORE,
        color=TEXT_TERTIARY,
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
                ft.Container(
                    content=ft.Icon(icon, color=PRIMARY, size=18),
                    width=32,
                    height=32,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=PRIMARY_CONTAINER,
                    border_radius=RADIUS_MD,
                ),
                ft.Column(
                    [
                        ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                        ft.Text(subtitle, size=12, color=TEXT_SECONDARY),
                    ],
                    spacing=1,
                    expand=True,
                ),
                chevron,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACING_LG, vertical=12),
        on_click=_toggle,
        ink=True,
    )

    return ft.Container(
        content=ft.Column([header, body], spacing=0),
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_MD,
        bgcolor=SURFACE_LOW,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


# ── 侧边栏 ───────────────────────────────────────────

def sidebar_item(label: str, icon: str, selected: bool = False) -> ft.Container:
    """侧边栏导航项"""
    bg = SIDEBAR_SELECTED if selected else "transparent"
    text_color = PRIMARY_HOVER if selected else TEXT_SECONDARY
    icon_color = PRIMARY if selected else TEXT_TERTIARY
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=icon_color, size=19),
                ft.Text(
                    label,
                    color=text_color,
                    size=13,
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                ),
            ],
            spacing=SPACING_SM,
        ),
        bgcolor=bg,
        border_radius=RADIUS_MD,
        padding=ft.Padding.symmetric(horizontal=SPACING_MD, vertical=11),
        on_click=None,  # 由外部绑定
        ink=True,
    )


def sidebar_group_label(text: str) -> ft.Container:
    """侧边栏分组标签"""
    return ft.Container(
        content=ft.Text(
            text,
            size=11,
            weight=ft.FontWeight.W_500,
            color=TEXT_TERTIARY,
        ),
        padding=ft.Padding.only(
            left=SPACING_MD,
            top=SPACING_LG,
            bottom=SPACING_XS,
        ),
    )


def empty_state(icon_name: str, title: str, hint: str) -> ft.Column:
    """标准化的空状态占位组件。"""
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        controls=[
            ft.Container(
                content=ft.Icon(icon_name, size=28, color=PRIMARY),
                width=56,
                height=56,
                alignment=ft.Alignment.CENTER,
                bgcolor=PRIMARY_CONTAINER,
                border_radius=RADIUS_LG,
            ),
            ft.Text(title, size=14, color=TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            ft.Text(hint, size=12, color=TEXT_TERTIARY),
        ],
    )


def table_container(*children, expand: bool = True, **kwargs) -> ft.Container:
    """标准化的表格容器，带边框、圆角和背景色。"""
    content = ft.Column(list(children), expand=True) if len(children) > 1 else children[0]
    return ft.Container(
        content=content,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=RADIUS_MD,
        padding=SPACING_XS,
        expand=expand,
        **kwargs,
    )
