// node --test dashboard/tests/validate.test.ts — S5 : validation imbriquee cote navigateur
import assert from "node:assert/strict";
import { test } from "node:test";
import { validateDashboardData } from "../src/validate.ts";

function valid(): Record<string, any> {
  const card = { evidence_id: "EV-a-TUN-2024", availability_status: "available", value: 37.8 };
  return {
    schema_version: "1.0", scope: { countries: [], kpis: [] }, catalog: { version: "1.6.0" },
    provenance: { warehouse_sha256: "x" }, publication_status: "approved",
    cards: [card], table: [{ ...card }], insights: [], notices: [],
    series: [{ points: [{ year: 2024, availability_status: "available", value: 37.8 },
                        { year: 2023, availability_status: "unavailable", value: null }] }],
    rankings: [{ rows: [{ rank: 1, availability_status: "available", value: 37.8 }] }],
    comparisons: [{ rows: [{ comparison_status: "complete", value: 1, reference_value: 2, difference: 1 }] }],
  };
}

test("un contrat valide passe", () => {
  assert.doesNotThrow(() => validateDashboardData(valid()));
});

const cases: [string, (d: Record<string, any>) => void, RegExp][] = [
  ["point non fini", (d) => { d.series[0].points[0].value = Infinity; }, /nombre fini/],
  ["point disponible vide", (d) => { d.series[0].points[0].value = null; }, /disponible non numérique/],
  ["point indisponible non nul", (d) => { d.series[0].points[1].value = 0; }, /non nulle/],
  ["valeur texte dans la table", (d) => { d.table[0].value = "37.8"; }, /nombre fini/],
  ["rang decimal", (d) => { d.rankings[0].rows[0].rank = 1.5; }, /rang entier/],
  ["comparaison complete sans ecart", (d) => { d.comparisons[0].rows[0].difference = null; }, /complète/],
  ["comparaison incomplete avec ecart", (d) => { d.comparisons[0].rows[0].comparison_status = "unavailable"; }, /incomplète/],
];
for (const [name, mutate, message] of cases) {
  test(`refuse : ${name}`, () => {
    const data = valid();
    mutate(data);
    assert.throws(() => validateDashboardData(data), message);
  });
}
