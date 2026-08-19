import fs from "node:fs";
import assert from "node:assert/strict";
import { Project } from "../js/core/project.js";
import * as M from "../js/core/model.js";

const doc = JSON.parse(fs.readFileSync(new URL("../data/reg01.json", import.meta.url), "utf8"));
const p = new Project();
p.loadFromRegulation(doc);
p.author = "자동 검증";

const v1 = p.currentId;
const target = M.flatten(p.tree).find((x) => x.node.level === "조" && x.node.no === 3).node;
p.select(target.id);
assert.equal(p.remove(), true, "조문 삭제가 실행되어야 한다");
assert.equal(M.findNode(p.tree, target.id), null, "삭제 조문은 현재 트리에서 없어야 한다");
assert.ok(p.allHistory({ versionId: v1 }).some((h) => h.kind === "삭제" && h.nodeId === target.id),
  "삭제된 조문의 이력이 이벤트 원장에 남아야 한다");

assert.equal(p.undo(), true, "삭제를 되돌릴 수 있어야 한다");
assert.ok(M.findNode(p.tree, target.id), "되돌리면 삭제 조문이 복원되어야 한다");
assert.ok(p.allHistory({ versionId: v1 }).some((h) => h.kind === "되돌림" && h.nodeId === target.id),
  "되돌림 감사 기록이 남아야 한다");

assert.equal(p.redo(), true, "삭제를 다시 실행할 수 있어야 한다");
assert.equal(M.findNode(p.tree, target.id), null, "다시 실행하면 조문이 삭제되어야 한다");
assert.ok(p.allHistory({ versionId: v1 }).some((h) => h.kind === "다시실행" && h.nodeId === target.id),
  "다시 실행 감사 기록이 남아야 한다");

const v2 = p.createVersion({ title: "삭제안 분기" });
assert.equal(v2.events.length, p.version(v1).events.length, "분기 버전이 선행 이력을 상속해야 한다");

const q = new Project();
q.fromJSON(JSON.parse(JSON.stringify(p.toJSON())));
assert.equal(q.version(v1).events.length, p.version(v1).events.length, "저장 왕복 후 v1 이력이 같아야 한다");
assert.equal(q.version(v2.id).events.length, v2.events.length, "저장 왕복 후 v2 이력이 같아야 한다");

console.log("PASS history ledger");
console.log(`versions=${q.versions.map((v) => `${v.label}:${v.events.length}`).join(",")}`);
