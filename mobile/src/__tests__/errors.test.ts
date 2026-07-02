import { describe, expect, it } from "vitest";

import { friendlyErrorMessage } from "../utils/errors";

describe("friendlyErrorMessage", () => {
  it("keeps UI errors localized even when backend messages are English", () => {
    expect(friendlyErrorMessage(new Error("Invalid credentials"), "登录失败")).toBe(
      "用户名或密码不正确",
    );
    expect(friendlyErrorMessage(new Error("Request failed"), "刷新失败")).toBe(
      "刷新失败",
    );
  });

  it("shows Chinese backend messages when available", () => {
    expect(friendlyErrorMessage(new Error("订单价格无效"), "下单失败")).toBe(
      "订单价格无效",
    );
  });
});
