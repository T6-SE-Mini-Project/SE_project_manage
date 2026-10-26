/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import StarRating from "./StarRating";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("StarRating (issue #11)", () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  function render(element: React.ReactElement) {
    container = document.createElement("div");
    document.body.appendChild(container);
    const currentRoot = createRoot(container);
    root = currentRoot;
    act(() => {
      currentRoot.render(element);
    });
    return container;
  }

  afterEach(() => {
    const currentRoot = root;
    if (currentRoot) {
      act(() => {
        currentRoot.unmount();
      });
    }
    container?.remove();
    root = null;
    container = null;
  });

  it("shows the rating as five stars with the earned ones filled", () => {
    const element = render(<StarRating value={4} />);

    const stars = element.querySelectorAll(".star");
    expect(stars).toHaveLength(5);
    expect(element.querySelectorAll(".star.filled")).toHaveLength(4);
  });

  it("describes an unrated book instead of showing a zero score", () => {
    const element = render(<StarRating value={null} />);

    expect(element.querySelector("[role='img']")?.getAttribute("aria-label"))
      .toBe("Not rated yet");
    expect(element.querySelectorAll(".star.filled")).toHaveLength(0);
  });

  it("renders radio inputs so a rating can be chosen with the keyboard", () => {
    const onChange = vi.fn();
    const element = render(<StarRating value={0} onChange={onChange} />);

    const inputs = element.querySelectorAll<HTMLInputElement>(
      "input[type='radio']",
    );
    expect(inputs).toHaveLength(5);
    expect(Array.from(inputs).map((input) => input.value)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
    ]);
  });

  it("reports the chosen rating", () => {
    const onChange = vi.fn();
    const element = render(<StarRating value={0} onChange={onChange} />);

    const fourth = element.querySelectorAll<HTMLInputElement>(
      "input[type='radio']",
    )[3];

    act(() => {
      fourth.click();
    });

    expect(onChange).toHaveBeenCalledWith(4);
  });
});
