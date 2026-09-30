import { describe, it, expect } from "vitest";
import { groupByDocument, CROSS_DOCUMENT } from "@/lib/group-findings";
import type { Finding } from "@/types/records";

const f = (id: string, doc: string, comparison: unknown[] = []): Finding =>
  ({ id, source: { doc }, comparison } as unknown as Finding);

describe("groupByDocument", () => {
  it("groups by source.doc, alphabetical, cross-document last", () => {
    const groups = groupByDocument([
      f("1", "TOR.pdf"),
      f("2", "DV.pdf"),
      f("3", "ignored", [{}, {}]), // 2+ comparison rows => cross-document
      f("4", "DV.pdf"),
    ]);
    expect(groups.map((g) => g.doc)).toEqual(["DV.pdf", "TOR.pdf", CROSS_DOCUMENT]);
    expect(groups[0].items.map((i) => i.id)).toEqual(["2", "4"]);
    expect(groups[2].items.map((i) => i.id)).toEqual(["3"]);
  });

  it("falls back to Unattributed when a finding has no source doc", () => {
    const groups = groupByDocument([{ id: "x", source: {} } as unknown as Finding]);
    expect(groups[0].doc).toBe("Unattributed");
  });
});
