import { useMemo } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatValue(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(3)
    : value;
}

export default function UnifiedLineChart({
  data = [],
  lines = [],
  xKey = "t",
  height = 220,
  theme = "dark",
  rightAxis = false,
  referenceLines = [],
  visible = null,
  onToggleLine = null,
  footnote = "",
  compact = false,
}) {
  const isLight = theme === "light";
  const axisColor = isLight ? "#56647a" : "#a69ec4";
  const tooltipBackground = isLight ? "#ffffff" : "#19064a";
  const tooltipBorder = isLight ? "#dce4f2" : "#35246b";
  const tooltipText = isLight ? "#182235" : "#ffffff";
  const chartData = useMemo(
    () =>
      data.map((row, index) => ({
        ...row,
        __chartX: row?.[xKey] ?? index + 1,
      })),
    [data, xKey]
  );
  const shownLines = lines.filter((line) => visible?.[line.key] !== false);
  const axisMaximum = (axis) => {
    const keys = shownLines
      .filter((line) => (line.axis || "left") === axis)
      .map((line) => line.key);
    const values = chartData.flatMap((row) =>
      keys.map((key) => row?.[key]).filter((value) => Number.isFinite(value))
    );
    const references = referenceLines
      .filter((reference) => (reference.axis || "left") === axis)
      .map((reference) => reference.value)
      .filter((value) => Number.isFinite(value));
    const maximum = Math.max(0, ...values, ...references);
    return maximum > 0 ? maximum * 1.08 : 1;
  };
  const leftMaximum = axisMaximum("left");
  const rightMaximum = axisMaximum("right");

  return (
    <div className={`line-chart${compact ? " line-chart-compact" : ""}`}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: rightAxis ? 8 : 12, bottom: 0, left: -12 }}
        >
          <XAxis
            dataKey="__chartX"
            stroke={axisColor}
            tick={{ fontSize: compact ? 9 : 10, fill: axisColor }}
            tickLine={false}
            axisLine={{ stroke: axisColor, strokeOpacity: 0.45 }}
            minTickGap={24}
          />
          <YAxis
            yAxisId="left"
            domain={[0, leftMaximum]}
            allowDataOverflow
            stroke={axisColor}
            tick={{ fontSize: compact ? 9 : 10, fill: axisColor }}
            tickFormatter={formatValue}
            tickLine={false}
            axisLine={false}
            width={compact ? 48 : 58}
          />
          {rightAxis && (
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, rightMaximum]}
              allowDataOverflow
              stroke={axisColor}
              tick={{ fontSize: 10, fill: axisColor }}
              tickFormatter={formatValue}
              tickLine={false}
              axisLine={false}
              width={58}
            />
          )}
          <Tooltip
            formatter={(value, name) => [formatValue(value), name]}
            contentStyle={{
              background: tooltipBackground,
              border: `1px solid ${tooltipBorder}`,
              borderRadius: "var(--radius-control)",
              color: tooltipText,
              fontSize: 11,
            }}
            labelStyle={{ color: tooltipText }}
            itemStyle={{ color: tooltipText }}
          />
          {referenceLines.map((reference) => (
            <ReferenceLine
              key={`${reference.axis || "left"}-${reference.value}`}
              yAxisId={reference.axis || "left"}
              y={reference.value}
              stroke={reference.color || axisColor}
              strokeDasharray={reference.dashed === false ? undefined : "3 3"}
            />
          ))}
          {shownLines.map((line) => (
            <Line
              key={line.key}
              yAxisId={line.axis || "left"}
              type="linear"
              dataKey={line.key}
              name={line.label || line.name}
              stroke={line.color}
              strokeWidth={line.width || 2}
              strokeDasharray={line.dashed ? "4 3" : undefined}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <div className="line-chart-legend">
        {lines.map((line) => {
          const enabled = visible?.[line.key] !== false;
          const content = (
            <>
              <i style={{ background: line.color }} />
              {line.label || line.name}
            </>
          );

          return onToggleLine ? (
            <button
              type="button"
              key={line.key}
              className={enabled ? "is-active" : ""}
              onClick={() => onToggleLine(line.key)}
            >
              {content}
            </button>
          ) : (
            <span key={line.key}>{content}</span>
          );
        })}
      </div>

      {footnote && <div className="line-chart-footnote">{footnote}</div>}
    </div>
  );
}
