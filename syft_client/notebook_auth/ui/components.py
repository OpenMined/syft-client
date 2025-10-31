"""Reusable UI components for notebook authentication."""

import ipywidgets as widgets


class UIComponents:
    """Reusable widget components extracted from scratch.py."""

    # CSS styles for cards
    CARD_STYLE = """
        <style>
            .gcp-card {
                background: white;
                border: 2px solid #4285f4;
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .gcp-title {
                color: #202124;
                font-size: 20px;
                font-weight: 500;
                margin: 0 0 15px 0;
            }
        </style>
    """

    @staticmethod
    def create_card(
        title: str, content_widgets: list, buttons: list = None
    ) -> widgets.VBox:
        """
        Create a styled card widget.

        Args:
            title: Card title
            content_widgets: List of widgets to display in card
            buttons: Optional list of button widgets

        Returns:
            VBox widget containing the card
        """
        title_html = widgets.HTML(
            value=f'{UIComponents.CARD_STYLE}<div class="gcp-card"><div class="gcp-title">{title}</div></div>'
        )

        elements = [title_html] + content_widgets

        if buttons:
            button_box = widgets.HBox(
                buttons, layout=widgets.Layout(margin="10px 0 0 0")
            )
            elements.append(button_box)

        return widgets.VBox(elements)

    @staticmethod
    def create_button(
        text: str, on_click=None, style: str = "primary", disabled: bool = False
    ) -> widgets.Button:
        """
        Create a styled button.

        Args:
            text: Button text
            on_click: Click handler function
            style: Button style ('primary', 'success', 'danger', etc.)
            disabled: Whether button is disabled

        Returns:
            Button widget
        """
        button_style_map = {
            "primary": "info",
            "success": "success",
            "danger": "danger",
            "warning": "warning",
            "": "",
        }

        btn = widgets.Button(
            description=text,
            button_style=button_style_map.get(style, ""),
            layout=widgets.Layout(width="auto", margin="5px"),
            disabled=disabled,
        )

        if on_click:
            btn.on_click(on_click)

        return btn

    @staticmethod
    def create_progress(
        message: str, percent: int = 50
    ) -> tuple[widgets.HTML, widgets.IntProgress]:
        """
        Create progress indicator with message.

        Args:
            message: Progress message
            percent: Progress percentage (0-100)

        Returns:
            Tuple of (HTML message widget, IntProgress widget)
        """
        message_widget = widgets.HTML(value=f"<p>{message}</p>")
        progress = widgets.IntProgress(value=percent, min=0, max=100, bar_style="info")

        return message_widget, progress

    @staticmethod
    def create_text_input(
        placeholder: str, multiline: bool = False, height: str = "200px"
    ) -> widgets.Textarea:
        """
        Create text input field.

        Args:
            placeholder: Placeholder text
            multiline: Whether to use textarea
            height: Height for multiline input

        Returns:
            Textarea widget
        """
        if multiline:
            return widgets.Textarea(
                placeholder=placeholder,
                layout=widgets.Layout(width="100%", height=height),
                style={"font_family": "monospace"},
            )
        else:
            return widgets.Text(
                placeholder=placeholder,
                layout=widgets.Layout(width="100%"),
            )

    @staticmethod
    def create_link_button(url: str, text: str) -> widgets.HTML:
        """
        Create clickable link styled as button.

        Args:
            url: URL to link to
            text: Button text

        Returns:
            HTML widget with styled link
        """
        return widgets.HTML(
            value=f"""
            <a href='{url}' target='_blank'
               style='display: inline-block; background: #4285f4; color: white;
                      padding: 12px 24px; border-radius: 6px; text-decoration: none;
                      font-size: 16px; margin: 10px 0;'>
                {text}
            </a>
            """
        )

    @staticmethod
    def create_status_html(message: str, type: str = "info") -> widgets.HTML:
        """
        Create status message with color coding.

        Args:
            message: Status message
            type: Message type ('success', 'error', 'warning', 'info')

        Returns:
            HTML widget with colored message
        """
        color_map = {
            "success": "#34a853",
            "error": "#d93025",
            "warning": "#f9ab00",
            "info": "#5f6368",
        }

        color = color_map.get(type, color_map["info"])

        return widgets.HTML(value=f"<p style='color: {color};'>{message}</p>")

    @staticmethod
    def create_checkbox(description: str, value: bool = False) -> widgets.Checkbox:
        """
        Create checkbox widget.

        Args:
            description: Checkbox label
            value: Initial value

        Returns:
            Checkbox widget
        """
        return widgets.Checkbox(
            value=value,
            description=description,
            indent=False,
            layout=widgets.Layout(margin="10px 0"),
        )

    @staticmethod
    def create_dropdown(
        options: list[str], description: str = "Select:"
    ) -> widgets.Dropdown:
        """
        Create dropdown selector.

        Args:
            options: List of options
            description: Dropdown label

        Returns:
            Dropdown widget
        """
        return widgets.Dropdown(
            options=options,
            description=description,
            layout=widgets.Layout(width="500px"),
        )

    @staticmethod
    def create_info_box(message: str, box_type: str = "info") -> widgets.HTML:
        """
        Create styled info/warning/success box.

        Args:
            message: Box content (supports HTML)
            box_type: Box type ('info', 'warning', 'success', 'error')

        Returns:
            HTML widget with styled box
        """
        style_map = {
            "info": {"bg": "#e8f5e9", "border": "#34a853", "color": "#1e7e34"},
            "warning": {"bg": "#fff3cd", "border": "#f9ab00", "color": "#856404"},
            "success": {"bg": "#e8f5e9", "border": "#34a853", "color": "#1e7e34"},
            "error": {"bg": "#f8d7da", "border": "#d93025", "color": "#721c24"},
        }

        style = style_map.get(box_type, style_map["info"])

        return widgets.HTML(
            value=f"""
            <div style='background: {style["bg"]}; border-left: 4px solid {style["border"]};
                        padding: 15px; border-radius: 4px; margin: 15px 0; color: {style["color"]};'>
                {message}
            </div>
            """
        )
