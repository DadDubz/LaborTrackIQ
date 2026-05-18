import { expect, test } from "@playwright/test";

test("public marketing pages render and footer links navigate", async ({ page }) => {
  await page.goto("/");
  const publicNav = page.getByLabel("Public site navigation");

  await expect(page.getByRole("heading", { name: "Scheduling, time clock, and labor control for restaurant teams." })).toBeVisible();
  await expect(publicNav.getByRole("button", { name: "Restaurant Login" })).toBeVisible();
  await expect(publicNav.getByRole("button", { name: "Learn More" })).toBeVisible();

  await publicNav.getByRole("button", { name: "Learn More" }).click();
  await expect(page.getByRole("heading", { name: "Restaurant labor tools for scheduling, time tracking, and team coordination." })).toBeVisible();

  await page.getByRole("button", { name: "Privacy" }).click();
  await expect(page.getByRole("heading", { name: "Privacy and data handling for restaurant teams." })).toBeVisible();

  await page.getByRole("button", { name: "Terms" }).click();
  await expect(page.getByRole("heading", { name: "Terms for using LaborTrackIQ." })).toBeVisible();
});

test("request access shows polished confirmation state", async ({ page }) => {
  await page.route("**/api/access-requests", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 101,
        restaurant_name: "Harbor Grill Group",
        contact_name: "Jamie Rivera",
        email: "jamie@example.com",
        locations: 3,
        current_tools: "7shifts",
        notes: "Need better payroll visibility.",
        status: "new",
        source: "website",
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.goto("/#about");
  await page.getByLabel("Restaurant or Group Name").fill("Harbor Grill Group");
  await page.getByLabel("Best Contact Name").fill("Jamie Rivera");
  await page.getByLabel("Contact Email").fill("jamie@example.com");
  await page.getByLabel("Number of Locations").fill("3");
  await page.getByLabel("Current Scheduling or Payroll Tools").fill("7shifts");
  await page.getByLabel("What do you want help with first?").fill("Need better payroll visibility.");
  await page.getByRole("button", { name: "Submit Request" }).click();

  await expect(page.getByRole("heading", { name: "Thanks, your request is in." })).toBeVisible();
  await expect(page.getByText("Harbor Grill Group")).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit Another Request" })).toBeVisible();
});

test("login help request shows support confirmation state", async ({ page }) => {
  await page.route("**/api/login-help-requests", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 201,
        organization_reference: "Org 12",
        email: "owner@example.com",
        details: "Need help signing in.",
        status: "new",
        source: "website",
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("Restaurant / Organization ID").last().fill("Org 12");
  await page.getByLabel("Contact Email").fill("owner@example.com");
  await page.getByLabel("What do you need help with?").fill("Need help signing in.");
  await page.getByRole("button", { name: "Request Login Help" }).click();

  await expect(page.getByText("We received your request and will follow up at")).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit Another Help Request" })).toBeVisible();
});
