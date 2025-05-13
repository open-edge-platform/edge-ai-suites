#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations
import gradio as gr
from collections.abc import Iterable
from gradio.themes.base import Base
from gradio.themes.utils import fonts, sizes
import datetime

class Color:
    all = []

    def __init__(
        self,
        c50: str,
        c100: str,
        c200: str,
        c300: str,
        c400: str,
        c500: str,
        c600: str,
        c700: str,
        c800: str,
        c900: str,
        c950: str = None,
        name: str | None = None,
    ):
        self.c50 = c50
        self.c100 = c100
        self.c200 = c200
        self.c300 = c300
        self.c400 = c400
        self.c500 = c500
        self.c600 = c600
        self.c700 = c700
        self.c800 = c800
        self.c900 = c900
        self.c950 = c950
        self.name = name
        Color.all.append(self)

    def expand(self) -> list[str]:
        return [
            self.c50, self.c100, self.c200, self.c300, self.c400,
            self.c500, self.c600, self.c700, self.c800, self.c900, self.c950
        ]

neutral = Color(
    name="neutral",
    c50="#ffffff",
    c100="#f9f9f9",
    c200="#f4f5f5",
    c300="#e9eaeb",
    c400="#e2e2e4",
    c500="#c9cace",
    c600="#b2b3b9",
    c700="#8b8e97",
    c800="#6a6d75",
    c900="#494b51",
    c950="#2b2c30",
)

classicblue = Color(
    name="classic-blue",
    c50="#ceebfc",
    c100="#9dd8f8",
    c200="#6cc4f5",
    c300="#368cd2",
    c400="#0099ec",
    c500="#0054ae",
    c600="#004a9d",
    c700="#00418d",
    c800="#00377c",
    c900="#001e50",
    c950="#001a45",
)

energyblue = Color(
    name="energy-blue",
    c50="#d0f5ff",
    c100="#a0ebff",
    c200="#87e4ff",
    c300="#6ddcff",
    c400="#00c7fd",
    c500="#0089b9",
    c600="#006e97",
    c700="#005374",
    c800="#00374d",
    c900="#001c27",
    c950="#00171f",
)

class SparkTheme(Base):
    def __init__(
        self,
        *,
        primary_hue: Color | str = classicblue,
        secondary_hue: Color | str = energyblue,
        neutral_hue: Color | str = neutral,
        spacing_size: sizes.Size | str = sizes.spacing_lg,
        radius_size: sizes.Size | str = sizes.radius_none,
        text_size: sizes.Size | str = sizes.text_lg,
        font: fonts.Font | str | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("Montserrat"),
            "ui-sans-serif",
            "sans-serif",
        ),
        font_mono: fonts.Font | str | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("Source Code Pro"),
            "ui-monospace",
            "Consolas",
            "monospace",
        ),
        # add core color for color_accent_dark
        color_accent_dark: str = "*secondary_400",
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )
        # add core color for color_accent_dark
        self.color_accent_dark = color_accent_dark

        self.name = "spark-island"
        
        super().set(
            # slider_color="*neutral_900",
            slider_color_dark="*secondary_400",
            # accordion_text_color="*body_text_color",
            # accordion_text_color_dark="*body_text_color",
            # table_text_color="*body_text_color",
            # table_text_color_dark="*body_text_color",
            body_text_color="*neutral_950", #updated
            block_label_text_color="*body_text_color",
            block_title_text_color="*body_text_color",
            body_text_color_subdued="*neutral_800", #updated
            # background_fill_primary_dark="*neutral_900",
            # background_fill_secondary_dark="*neutral_800",
            # block_background_fill_dark="*neutral_800",
            # input_background_fill_dark="*neutral_700",
            button_border_width="2px",
            # button_primary_border_color="*neutral_900",
            button_primary_background_fill="*primary_500",
            button_primary_background_fill_hover="*primary_700",
            # button_primary_text_color="white",
            button_primary_background_fill_dark="*secondary_400",
            button_primary_background_fill_hover_dark="*secondary_300",
            button_primary_text_color_dark="*neutral_950",

            #button secondary
            button_secondary_border_color="*primary_500",
            button_secondary_border_color_hover="*primary_700",

            button_secondary_background_fill="white",
            button_secondary_background_fill_hover="white",
            button_secondary_background_fill_dark="*neutral_950",
            
            button_secondary_text_color="*primary_500",
            button_secondary_text_color_hover="*primary_700",

            button_secondary_border_color_dark="*secondary_400",
            button_secondary_text_color_dark="*secondary_400",
            # button_cancel_border_color="*neutral_900",
            # button_cancel_background_fill="*button_secondary_background_fill",
            # button_cancel_background_fill_hover="*button_secondary_background_fill_hover",
            # button_cancel_text_color="*button_secondary_text_color",
            # checkbox_label_border_color="*checkbox_background_color",
            # checkbox_label_border_color_hover="*button_secondary_border_color_hover",
            # checkbox_label_border_color_selected="*button_primary_border_color",
            # checkbox_label_border_width="*button_border_width",
            # checkbox_background_color="*input_background_fill",
            # checkbox_label_background_fill_selected="*button_primary_background_fill",
            # checkbox_label_text_color_selected="*button_primary_text_color",
            # checkbox_label_padding="*spacing_sm",
            # button_large_padding="*spacing_lg",
            # button_small_padding="*spacing_sm",
            # shadow_drop_lg="0 1px 4px 0 rgb(0 0 0 / 0.1)",
            # block_shadow="none",
            # block_shadow_dark="*shadow_drop_lg",
            # block_title_text_weight="500",
            # block_label_text_weight="400",
            # block_label_text_size="*text_md",
            prose_header_text_weight = "200",
            button_large_text_weight = "500",
            button_medium_text_weight = "500",
            button_small_text_weight = "500",
            stat_background_fill_dark="*secondary_400",
            )
    
    @staticmethod
    def header(title: str = "Demo App"):
        return gr.HTML(f"<div class=\"spark-header-line\"></div><div class=\"spark-header\"><img src=\"https://www.intel.com/content/dam/logos/intel-header-logo.svg\" class=\"spark-logo\"></img><div class=\"spark-title\">{title}</div></div>")

    @staticmethod
    def footer(content: str = f"©{datetime.datetime.now().year} Intel Corporation. All rights reserved."):
        return gr.HTML(f"<div class=\"spark-footer\"><div class=\"spark-footer-info\">{content}</div></div>")

    def load_css(self):
        css = f"""
        main{{
            padding: 0px;
        }}
        .spark-header-line {{
            width: 100%;
            height: 10px;
            background: rgb(0, 199, 253);
            background: linear-gradient(
                90deg,
                #1db0e2 5%,
                #4ca286 50%,
                #89ad4e 98.99%
            );
        }}

        .spark-header {{
            margin: 0px;
            padding: 0px;
            background: {self.primary_500};
            height: 60px;
        }}
        .spark-logo {{
            margin-left: 20px;
            margin-right: 20px;
            width: 60px;
            height: 60px;
            float: left;
        }}
        .spark-title {{
            height: 60px;
            line-height: 60px;
            float: left;
            color: white;
            font-weight: var(--prose-header-text-weight);
            font-size: 24px;   
        }}
        .html-container {{
            padding: 0;
        }}
        .header {{
            margin: 0px;
            padding: 10px;
            background: {self.primary_500};
            color: white;
            font-size: 24px;
        }}
        .spark-footer {{
            background: {self.primary_500};
            height: 40px;
            justify-content: center;
            align-items: center;
        }}
        .spark-footer-info {{
            margin-left: auto;
            margin-right: auto;
            height: 40px;
            line-height: 40px;
            color: white;
            font-size: 18px;
            text-align: center;
        }}
        footer {{display: none !important}}
        """      
        return css
