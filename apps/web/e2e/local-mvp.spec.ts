import { expect, test } from "@playwright/test";

test("Product Owner can complete the local Mock MVP flow", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");
  await expect(page.getByTestId("project-form")).toBeVisible();
  await page.getByLabel("短剧标题").fill("夜航灯");
  await page.getByLabel("一句话故事创意").fill("夜班船员发现一盏不该亮起的旧灯，顺着它找回失踪的哥哥。");
  await page.getByTestId("start-production").click();
  await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("rough-cut")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("ROUGH_CUT_READY")).toBeVisible();

  await page.getByRole("button", { name: /分镜/ }).click();
  await expect(page.getByText("shot-15")).toBeVisible();
  const regenerateButtons = page.getByRole("button", { name: "重新生成" });
  await regenerateButtons.nth(2).click();
  const replaceButtons = page.getByRole("button", { name: "替换候选" });
  await expect(replaceButtons.nth(2)).toBeEnabled();
  await replaceButtons.nth(2).click();
  await expect(page.getByText(/时间线已更新/)).toBeVisible();

  await page.getByRole("button", { name: "编辑 shot-3 台词" }).click();
  await expect(page.getByText(/台词已更新/)).toBeVisible();
  await page.getByRole("button", { name: "运行自动修复上限" }).click();
  await expect(page.getByText(/Issue 已转人工处理/)).toBeVisible();

  await page.getByRole("button", { name: "证据 \/ Issue" }).click();
  await expect(page.getByText("CREATIVE_REPAIR_LIMIT")).toBeVisible();
  await page.getByRole("button", { name: "成本" }).click();
  await expect(page.getByText("is_mock=true")).toBeVisible();
});

