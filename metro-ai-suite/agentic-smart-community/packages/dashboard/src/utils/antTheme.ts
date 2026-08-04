// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
import { theme } from "ant-design-vue";
export const antTheme = {
  black: {
    token: {
      colorPrimary: "#111111",
    },
  },
  subTheme: {
    token: {
      colorPrimary: "#0054AE",
    },
  },
  success: {
    token: {
      colorPrimary: "#008A00",
    },
  },
  danger: {
    token: {
      colorPrimary: "#ce0000",
    },
  },
  light: {
    algorithm: theme.defaultAlgorithm,
    inherit: false,
    token: {
      colorPrimary: "#00377C",
      colorPrimaryBg: "#E0EAFF",
      colorError: "#EA0000",
      colorInfo: "#AAAAAA",
      colorSuccess: "#179958",
      colorWarning: "#faad14",
      colorTextBase: "#131313",
      colorSuccessBg: "#D6FFE8",
      colorWarningBg: "#feefd0",
      colorErrorBg: "#FFA3A3",
      colorInfoBg: "#EEEEEE",
    },
    cssVar: true,
  },
  dark: {
    algorithm: theme.darkAlgorithm,
    inherit: false,
    token: {
      colorPrimary: "#1668dc",
      colorPrimaryBg: "#16243b",
      colorError: "#ff7875",
      colorInfo: "#8b95a7",
      colorSuccess: "#179958",
      colorWarning: "#e18a2d",
      colorTextBase: "#f3f4f6",
      colorBgBase: "#171c24",
      colorBgContainer: "#222831",
      colorBorder: "#3b4556",
      colorSuccessBg: "#173a29",
      colorWarningBg: "#463114",
      colorErrorBg: "#51292d",
      colorInfoBg: "#232830",
    },
    cssVar: true,
  },
};
