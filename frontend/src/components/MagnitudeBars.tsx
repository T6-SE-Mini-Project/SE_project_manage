/**
 * Horizontal bars for one measure across categories.
 *
 * A single measure, so one hue is used for every bar: colour carries no
 * extra meaning here and the value label on each bar is the identity, so
 * no legend is needed. Bars are anchored to a common baseline, which is
 * what makes their lengths comparable.
 */
interface MagnitudeBarsProps {
  rows: { key: string; label: string; value: number; display?: string }[];
  /** Describes what the bar lengths mean, for assistive technology. */
  caption: string;
}

export default function MagnitudeBars({ rows, caption }: MagnitudeBarsProps) {
  const max = Math.max(...rows.map((row) => row.value), 0);

  return (
    <ul className="magnitude-bars" aria-label={caption}>
      {rows.map((row) => (
        <li key={row.key}>
          <span className="magnitude-label">{row.label}</span>
          <span className="magnitude-track">
            <span
              className="magnitude-fill"
              style={{ width: max > 0 ? `${(row.value / max) * 100}%` : "0%" }}
            />
          </span>
          <span className="magnitude-value">{row.display ?? row.value}</span>
        </li>
      ))}
    </ul>
  );
}
