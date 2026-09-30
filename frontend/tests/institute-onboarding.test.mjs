import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const resourceSource = await readFile(
  new URL("../src/lib/resources.ts", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(resourceSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
});
const { fieldsFor } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const pageSource = await readFile(
  new URL("../src/app/portal/[module]/page.tsx", import.meta.url),
  "utf8",
);
const ast = ts.createSourceFile(
  "page.tsx",
  pageSource,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);
let createSource;
function visit(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === "createInstitute")
    createSource = node.getText(ast);
  ts.forEachChild(node, visit);
}
visit(ast);
const scope = { students: [], batches: [], subjects: [] };

test("creation asks for one required email and delegates Admin email seeding to the backend", async () => {
  let editor;
  let sent;
  const create = new Function(
    "fieldsFor",
    "scope",
    "catalogs",
    "setEdit",
    "mutate",
    `${createSource}; return createInstitute;`,
  )(
    fieldsFor,
    scope,
    {},
    (value) => {
      editor = value;
    },
    async (path, data) => {
      sent = { path, data };
    },
  );
  create();
  const emails = editor.fields.filter((field) => field.type === "email");
  assert.equal(emails.length, 1);
  assert.equal(emails[0].name, "email");
  assert.equal(emails[0].required, true);
  await editor.save({
    name: "Example",
    email: "owner@example.invalid",
    admin_name: "Owner",
    admin_username: "owner",
  });
  assert.equal(sent.path, "/api/super-admin/institutes/");
  assert.equal(sent.data.email, "owner@example.invalid");
  assert.deepEqual(sent.data.initial_admin, {
    full_name: "Owner",
    username: "owner",
    role: "ADMIN",
  });
  assert.equal("admin_name" in sent.data, false);
});

test("existing institute contact email remains optional when editing", () => {
  const fields = fieldsFor("institutes", scope, {}, "SUPER_ADMIN");
  assert.equal(fields.find((field) => field.name === "email").required, false);
});

function adminEditor(dependencies) {
  let editorSource;
  function find(node) {
    if (
      ts.isObjectLiteralExpression(node) &&
      node.properties.some(
        (property) =>
          ts.isPropertyAssignment(property) &&
          property.name.getText(ast) === "title" &&
          ts.isStringLiteral(property.initializer) &&
          property.initializer.text === "Edit Admin",
      )
    )
      editorSource = node.getText(ast);
    ts.forEachChild(node, find);
  }
  find(ast);
  const { outputText: compiled } = ts.transpileModule(
    `const editor = ${editorSource};`,
    {
      compilerOptions: { target: ts.ScriptTarget.ES2022 },
    },
  );
  return new Function(
    ...Object.keys(dependencies),
    `${compiled}; return editor;`,
  )(...Object.values(dependencies));
}

test("Admin editor restricts fields, patches the selected account, and refreshes details", async () => {
  const calls = [];
  const refreshed = {
    id: 7,
    admin_accounts: [{ id: 11, email: "updated@example.invalid" }],
  };
  let shown;
  let reloads = 0;
  let notice;
  const editor = adminEditor({
    detail: { id: 7 },
    account: { id: 11 },
    api: async (...args) => {
      calls.push(args);
      return refreshed;
    },
    setDetail: (value) => {
      shown = value;
    },
    reload: () => {
      reloads++;
    },
    setNotice: (value) => {
      notice = value;
    },
  });
  assert.deepEqual(
    editor.fields.map((field) => field.name),
    ["full_name", "email", "phone"],
  );
  const values = {
    full_name: "Owner",
    email: "updated@example.invalid",
    phone: "123",
  };
  await editor.save(values);
  assert.deepEqual(calls, [
    ["/api/super-admin/institutes/7/admin_accounts/11/", "PATCH", values],
    ["/api/super-admin/institutes/7/"],
  ]);
  assert.equal(shown, refreshed);
  assert.equal(reloads, 1);
  assert.equal(notice, "Admin account updated.");
});

test("Admin save propagates validation failures to the existing Editor", async () => {
  const fail = () =>
    assert.fail("Must not report success after rejected update");
  const editor = adminEditor({
    detail: { id: 7 },
    account: { id: 11 },
    api: async () => {
      throw new Error("email: Enter a valid email address.");
    },
    setDetail: fail,
    reload: fail,
    setNotice: fail,
  });
  await assert.rejects(
    editor.save({ email: "invalid" }),
    /email: Enter a valid email/,
  );
});
