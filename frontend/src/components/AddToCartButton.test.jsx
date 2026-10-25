/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import AddToCartButton from "./AddToCartButton";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("AddToCartButton (TC-OBS-022)", () => {
  let container;
  let root;

  afterEach(() => {
    if (root) {
      act(() => {
        root.unmount();
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
    root = createRoot(container);

    act(() => {
      root.render(<AddToCartButton onAdd={onAdd} />);
    });

    const button = container.querySelector("button");
    expect(button.textContent).toMatch(/add to cart/i);

    act(() => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(onAdd).toHaveBeenCalledTimes(1);
  });
});
