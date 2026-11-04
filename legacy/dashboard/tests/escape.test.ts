// node --test dashboard/tests/escape.test.ts (Node >= 22.6, types retires a la volee)
import assert from "node:assert/strict";
import { test } from "node:test";
import { escapeHtml } from "../src/escape.ts";

test("un libelle HTML malveillant reste du texte", () => {
  const name = '<img src=x onerror="alert(1)">Tunisie & co\'';
  const safe = escapeHtml(name);
  assert.equal(safe, "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;Tunisie &amp; co&#39;");
  assert.ok(!safe.includes("<") && !safe.includes(">"));
});

test("valeurs vides ou non textuelles", () => {
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(undefined), "");
  assert.equal(escapeHtml(2024), "2024");
});
