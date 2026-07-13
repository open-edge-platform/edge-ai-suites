import React from "react";

interface TooltipProps {
  text: string;
}

const Tooltip: React.FC<TooltipProps> = ({ text }) => (
  <span
    style={{
      display: "inline-block",
      marginLeft: 4,
      background: "#eee",
      color: "#333",
      borderRadius: 4,
      padding: "2px 6px",
      fontSize: "0.85em",
      cursor: "help",
      border: "1px solid #ccc",
    }}
    title={text}
  >
    ?
  </span>
);

export default Tooltip;