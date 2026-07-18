import { expect, test, type Page } from "@playwright/test";

async function mockCommonApi(page: Page) {
  await page.route("**/api/csrf", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrf_token: "test-csrf" }) })
  );
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "test-access-token" }) })
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        email: "owner@example.test",
        name: "Owner",
        role: "owner",
        locale: "hu",
        theme: "light",
        tenant_kb_has_training: true,
      }),
    })
  );
  await page.route("**/api/auth/default-settings", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ locale: "hu", theme: "light" }) })
  );
  await page.route("**/api/settings", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        two_factor_enabled: false,
        timezone: "Europe/Budapest",
        date_format: "YYYY-MM-DD",
        time_format: "HH:mm",
      }),
    })
  );
  await page.route("**/api/traffic/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        limits: { questions_monthly: 500, training_chars_available: 500000 },
        training: { available_training_chars: 500000, trained_chars: 0 },
        questions: { available_total: 500, used_total: 0 },
      }),
    })
  );
}

function mockKbList(page: Page) {
  return page.route("**/api/kb", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          uuid: "kb-1",
          name: "E2E KB",
          description: "",
          status: "active",
          can_train: true,
          storage_metrics: { total_bytes: 0, file_bytes: 0, database_bytes: 0, qdrant_bytes: 0, training_char_count: 1200 },
        },
      ]),
    })
  );
}

const sourcePayload = {
  kb_uuid: "kb-1",
  kb_name: "E2E KB",
  point_id: "chunk-abc",
  source_id: "chunk-abc",
  citation_id: "CIT-1",
  title: "HR kézikönyv",
  snippet: "Évente 20 nap szabadság jár.",
  download_url: "/api/chat/sources/qry_1/chunk-abc/download",
  download_url_template: "/api/chat/sources/{query_run_id}/{source_id}/download",
  download_ref: "source:chunk-abc",
  page_numbers: [12],
  section_title: "Szabadság",
};

test.beforeEach(async ({ page }) => {
  await mockCommonApi(page);
  await mockKbList(page);
});

test("source modal megjelenik answered válasznál", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Évente 20 nap szabadság jár.",
        answer_mode: "answered",
        query_run_id: "qry_1",
        sources: [sourcePayload],
        citation_records: [sourcePayload],
        citations: ["CIT-1"],
      }),
    })
  );
  await page.goto("/chat");
  await page.getByRole("textbox").fill("Mennyi szabadság jár?");
  await page.getByRole("button", { name: /küld|send/i }).click();
  await expect(page.getByText("Évente 20 nap szabadság jár.")).toBeVisible();
  await page.getByRole("button", { name: /forrás|source/i }).first().click();
  await expect(page.getByText("HR kézikönyv")).toBeVisible();
  await expect(page.getByText("CIT-1")).toBeVisible();
});

test("no-answer állapot nem mutat forrás gombot", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Nincs elegendő információ a válaszhoz.",
        answer_mode: "no_answer",
        sources: [],
      }),
    })
  );
  await page.goto("/chat");
  await page.getByRole("textbox").fill("Ismeretlen kérdés?");
  await page.getByRole("button", { name: /küld|send/i }).click();
  await expect(page.getByText("Nincs elegendő információ")).toBeVisible();
  await expect(page.getByRole("button", { name: /forrás|source/i })).toHaveCount(0);
});

test("not-ready állapot readiness üzenetet mutat", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "A tudástár még nem kereshető.",
        answer_mode: "blocked_not_ready",
        sources: [],
        readiness: { blocking_issues: ["qdrant_not_verified"] },
      }),
    })
  );
  await page.goto("/chat");
  await page.getByRole("textbox").fill("Teszt?");
  await page.getByRole("button", { name: /küld|send/i }).click();
  await expect(page.getByText(/nem kereshető|not ready/i)).toBeVisible();
});

test("source download hívás elindul", async ({ page }) => {
  let downloadRequested = false;
  await page.route("**/api/chat/sources/qry_1/chunk-abc/download", (route) => {
    downloadRequested = true;
    route.fulfill({
      status: 200,
      contentType: "text/plain",
      body: "Citation: CIT-1\nDokumentum: HR kézikönyv",
      headers: { "Content-Disposition": "attachment; filename=source-CIT-1.txt" },
    });
  });
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Évente 20 nap szabadság jár.",
        answer_mode: "answered",
        query_run_id: "qry_1",
        sources: [sourcePayload],
      }),
    })
  );
  await page.goto("/chat");
  await page.getByRole("textbox").fill("Mennyi szabadság?");
  await page.getByRole("button", { name: /küld|send/i }).click();
  await page.getByRole("button", { name: /forrás|source/i }).first().click();
  await page.getByRole("button", { name: /letölt|download/i }).first().click();
  await expect.poll(() => downloadRequested).toBe(true);
});
