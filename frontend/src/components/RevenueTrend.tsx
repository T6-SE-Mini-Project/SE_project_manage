/**
 * Daily revenue over the reported period (issue #24).
 *
 * One measure over time, so it is a single-series line on one axis, drawn
 * as inline SVG to avoid a charting dependency. One series needs no
 * legend: the figure's caption names it. Each point carries a <title> so
 * hovering (and assistive technology) gives the exact value, and the
 * table under the chart is the accessible equivalent of the whole series.
 */
import { formatPrice } from "../format";

interface RevenuePoint {
  date: string;
  order_count: number;
  revenue: string;
}

interface RevenueTrendProps {
  points: RevenuePoint[];
}

const WIDTH = 720;
const HEIGHT = 220;
const PADDING = { top: 16, right: 16, bottom: 32, left: 56 };

function shortDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function RevenueTrend({ points }: RevenueTrendProps) {
  if (points.length === 0) {
    return <p className="muted">No revenue was recorded in this period.</p>;
  }

  const values = points.map((point) => Number(point.revenue));
  const max = Math.max(...values);
  // A flat series would divide by zero; fall back to a 1-unit scale.
  const scaleMax = max > 0 ? max : 1;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const x = (index: number) =>
    points.length === 1
      ? PADDING.left + plotWidth / 2
      : PADDING.left + (index / (points.length - 1)) * plotWidth;
  const y = (value: number) =>
    PADDING.top + plotHeight - (value / scaleMax) * plotHeight;

  const line = points
    .map((point, index) => `${x(index)},${y(Number(point.revenue))}`)
    .join(" ");
  const area = `${PADDING.left},${PADDING.top + plotHeight} ${line} ${
    x(points.length - 1)
  },${PADDING.top + plotHeight}`;

  // Three recessive gridlines are enough to read magnitude.
  const ticks = [0, 0.5, 1].map((fraction) => ({
    value: scaleMax * fraction,
    y: y(scaleMax * fraction),
  }));

  return (
    <figure className="chart-figure">
      <svg
        className="chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Daily revenue, ${points.length} day${
          points.length === 1 ? "" : "s"
        }, peak ${formatPrice(max)}`}
      >
        {ticks.map((tick) => (
          <g key={tick.value}>
            <line
              className="chart-grid"
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={tick.y}
              y2={tick.y}
            />
            <text className="chart-axis-label" x={PADDING.left - 8} y={tick.y + 4} textAnchor="end">
              {formatPrice(tick.value)}
            </text>
          </g>
        ))}

        {points.length > 1 ? (
          <polygon className="chart-area" points={area} />
        ) : null}
        <polyline className="chart-line" points={line} />

        {points.map((point, index) => (
          <g key={point.date}>
            <circle
              className="chart-point"
              cx={x(index)}
              cy={y(Number(point.revenue))}
              r={5}
            />
            <title>
              {`${shortDate(point.date)}: ${formatPrice(point.revenue)} from ${
                point.order_count
              } order${point.order_count === 1 ? "" : "s"}`}
            </title>
          </g>
        ))}

        {/* Label the ends only; a value on every point is unreadable. */}
        <text
          className="chart-axis-label"
          x={PADDING.left}
          y={HEIGHT - 10}
          textAnchor="start"
        >
          {shortDate(points[0].date)}
        </text>
        {points.length > 1 ? (
          <text
            className="chart-axis-label"
            x={WIDTH - PADDING.right}
            y={HEIGHT - 10}
            textAnchor="end"
          >
            {shortDate(points[points.length - 1].date)}
          </text>
        ) : null}
      </svg>
      <figcaption>
        Revenue per day over the reported period. Peak {formatPrice(max)}.
      </figcaption>
    </figure>
  );
}
