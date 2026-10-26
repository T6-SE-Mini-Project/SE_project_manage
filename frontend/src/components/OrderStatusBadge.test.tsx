/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import OrderStatusBadge from "./OrderStatusBadge";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("OrderStatusBadge (issue #10)", () => {
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

  it("shows the label the server supplied", () => {
    const element = render(
      <OrderStatusBadge status="PENDING" label="Pending payment" />,
    );

    expect(element.textContent).toBe("Pending payment");
  });

  it("falls back to the raw status when no label is given", () => {
    const element = render(<OrderStatusBadge status="DELIVERED" />);

    expect(element.textContent).toBe("DELIVERED");
  });

  it("distinguishes a cancelled order from a completed one", () => {
    const cancelled = render(<OrderStatusBadge status="CANCELLED" />)
      .querySelector(".badge")
      ?.className;

    act(() => {
      root?.unmount();
    });
    container?.remove();
    root = null;

    const delivered = render(<OrderStatusBadge status="DELIVERED" />)
      .querySelector(".badge")
      ?.className;

    expect(cancelled).not.toBe(delivered);
  });
});
