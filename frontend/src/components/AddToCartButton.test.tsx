/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import AddToCartButton from "./AddToCartButton";

declare global {
  // React's act() requires this flag in test environments.
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("AddToCartButton (TC-OBS-022)", () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  afterEach(() => {
    const currentRoot = root;
    if (currentRoot) {
      act(() => {
        currentRoot.unmount();
      });
    }
    if (container) {
      container.remove();
    }
    root = null;
    container = null;
  });

  it("adds a book to the cart with one primary interaction", () => {
    const onAdd = vi.fn();

    container = document.createElement("div");
    document.body.appendChild(container);
    const currentRoot = createRoot(container);
    root = currentRoot;

    act(() => {
      currentRoot.render(<AddToCartButton onAdd={onAdd} />);
    });

    const button = container.querySelector("button")!;
    expect(button.textContent).toMatch(/add to cart/i);

    act(() => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(onAdd).toHaveBeenCalledTimes(1);
  });
});
