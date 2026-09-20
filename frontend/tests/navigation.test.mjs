import assert from "node:assert/strict";
import test from "node:test";
import { canOpen, navigation } from "../src/lib/navigation.ts";

test("approved navigation counts and role restrictions", () => {
  for (const [role, count] of Object.entries({
    ADMIN: 13,
    TEACHER: 9,
    STUDENT: 9,
    PARENT: 8,
    SUPER_ADMIN: 6,
  })) {
    assert.equal(navigation[role].length, count);
    assert.equal(new Set(navigation[role].map(([key]) => key)).size, count);
  }
  assert.equal(canOpen("TEACHER", "fees"), false);
  assert.equal(canOpen("TEACHER", "parents"), false);
  assert.equal(canOpen("PARENT", "timetable"), false);
  assert.equal(canOpen("STUDENT", "students"), false);
  assert.equal(canOpen("SUPER_ADMIN", "results"), false);
});
